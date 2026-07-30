import json
import os
import time
from typing import Generator, Dict, Any, List, Optional
from pydantic import BaseModel, Field
from playwright.sync_api import sync_playwright
from google import genai
from google.genai import types

# Pydantic models for Gemini structured output
class SurveyAction(BaseModel):
    id: int = Field(description="The index number assigned to the element in the screenshot/metadata.")
    action: str = Field(description="Action to perform: 'fill' (for text/textarea/number/date inputs) or 'click' (for radio buttons, checkboxes, dropdown items, or buttons).")
    value: Optional[str] = Field(description="The value to fill for 'fill' action (e.g. text input content), or null for 'click' action.")

class GeminiSurveyResponse(BaseModel):
    reasoning: str = Field(description="Short rationale explaining how the choices fit the target persona.")
    actions: List[SurveyAction] = Field(description="List of filling and selection actions to execute on the form fields.")
    navigation_action_id: Optional[int] = Field(description="The ID of the button (e.g., 'Next', 'Submit', 'Continue') to click after filling out all the fields on this page. Should be null if no button needs to be clicked yet.")

def run_survey_filler(
    url: str, 
    persona: str, 
    api_key: str, 
    model_name: str = "gemma-4-31b-it",
    max_steps: int = 30,
    headless: bool = True
) -> Generator[Dict[str, Any], None, None]:
    """
    Runs the survey filling agent using Playwright and the Gemini API.
    Yields dictionary updates representing agent steps and state.
    """
    # 1. Initialize Google GenAI client
    if not api_key:
        yield {"status": "error", "message": "Google Gemini API Key is required."}
        return
        
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        yield {"status": "error", "message": f"Failed to initialize Gemini Client: {str(e)}"}
        return

    # Read the annotation script
    annotation_js_path = os.path.join(os.path.dirname(__file__), "annotation.js")
    try:
        with open(annotation_js_path, "r", encoding="utf-8") as f:
            annotation_js = f.read()
    except Exception as e:
        yield {"status": "error", "message": f"Failed to read annotation.js: {str(e)}"}
        return

    yield {"status": "info", "message": "Launching browser..."}

    with sync_playwright() as p:
        try:
            # We use a custom user agent to appear as a normal browser
            browser = p.chromium.launch(
                headless=headless,
                args=["--disable-web-security", "--no-sandbox"]
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            yield {"status": "info", "message": f"Navigating to {url}..."}
            page.goto(url, wait_until="load", timeout=30000)
            # Give a brief delay for any dynamic hydration
            page.wait_for_timeout(2000)
            
            step_count = 0
            
            while step_count < max_steps:
                step_count += 1
                yield {"status": "info", "message": f"Analyzing page (Step {step_count}/{max_steps})..."}
                
                # Execute annotation JS
                elements = page.evaluate(annotation_js)
                
                # Wait briefly for annotations to render in browser
                page.wait_for_timeout(500)
                
                # Take screenshot of the page with badges
                screenshot_bytes = page.screenshot(type="png", full_page=False)
                
                # Yield current step info with screenshot before filling
                yield {
                    "status": "step_start",
                    "step": step_count,
                    "screenshot": screenshot_bytes,
                    "elements": elements,
                    "message": f"Page analyzed. Found {len(elements)} interactive elements."
                }
                
                # If there are no elements, we might have completed the survey
                if not elements:
                    # Let's inspect page text to check if it's a completion page
                    body_text = page.inner_text("body").lower()
                    completion_keywords = ["recorded", "thank you", "submitted", "done", "response", "completed", "success"]
                    is_completed = any(kw in body_text for kw in completion_keywords)
                    
                    if is_completed:
                        yield {
                            "status": "success", 
                            "message": "Survey completed successfully! Confirmation page detected.",
                            "screenshot": screenshot_bytes
                        }
                    else:
                        yield {
                            "status": "error",
                            "message": "No input elements found and confirmation page was not detected.",
                            "screenshot": screenshot_bytes
                        }
                    break

                # Prepare Gemini Prompt
                elements_json_str = json.dumps(elements, indent=2)
                prompt = f"""You are an AI survey agent mimicking a specific persona.
Your objective is to fill out this page of the survey based on the persona.

TARGET PERSONA:
{persona}

Below is the list of elements detected on this page (each element is annotated with a red badge containing its ID):
{elements_json_str}

Instructions:
1. Examine the screenshot and the list of elements carefully.
2. For each question, decide on the appropriate answer that matches the target persona. Be consistent with their demographic, style, tone, and opinions.
3. For text/textarea inputs (type: 'text' or 'textarea'), output a 'fill' action with the response text.
4. For number or date inputs, output a 'fill' action with a valid value.
5. For radio, checkbox, dropdown, or option elements (type: 'radio', 'checkbox', 'dropdown'), output a 'click' action on the element matching the desired choice.
   - For Checkboxes: Check the 'checked' field in the element metadata. ONLY output a 'click' action if you need to toggle the checkbox to match your desired state. E.g., if you want it selected and it's currently false, output 'click'. If it is already true, do not click it.
6. Look for a button (type: 'button', usually labeled 'Next', 'Submit', 'Continue', 'Submit response') that moves to the next page or submits the form. Specify its ID in 'navigation_action_id'. ONLY include this if you have filled out all required fields on the current page. If the page is a completion screen, do not specify any actions or navigation.
7. Provide a concise explanation of your decisions in the 'reasoning' field.
"""

                yield {"status": "info", "message": "Consulting Gemini API for actions..."}
                
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[
                            prompt,
                            types.Part.from_bytes(data=screenshot_bytes, mime_type="image/png")
                        ],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=GeminiSurveyResponse,
                            temperature=0.2
                        )
                    )
                    
                    # Parse response
                    ai_response = GeminiSurveyResponse.model_validate_json(response.text)
                except Exception as e:
                    yield {"status": "error", "message": f"Gemini API error: {str(e)}"}
                    break

                yield {
                    "status": "ai_response",
                    "reasoning": ai_response.reasoning,
                    "actions": [a.model_dump() for a in ai_response.actions],
                    "navigation_action_id": ai_response.navigation_action_id
                }

                # Execute actions
                if ai_response.actions:
                    yield {"status": "info", "message": f"Executing {len(ai_response.actions)} actions..."}
                    for action in ai_response.actions:
                        el_id = action.id
                        action_type = action.action
                        action_val = action.value
                        
                        # Find the corresponding element in window.surveyElements
                        # ID is 1-indexed, array is 0-indexed
                        try:
                            element_handle = page.evaluate_handle(f"window.surveyElements[{el_id - 1}]")
                            if not element_handle:
                                yield {"status": "warning", "message": f"Could not find element handle for ID {el_id}"}
                                continue
                            
                            # Get element details for logging
                            tag_name = page.evaluate(f"window.surveyElements[{el_id - 1}].tagName").lower()
                            
                            if action_type == 'fill':
                                yield {"status": "info", "message": f"Filling element [{el_id}] with '{action_val}'"}
                                element_handle.focus()
                                element_handle.fill(action_val)
                            elif action_type == 'click':
                                yield {"status": "info", "message": f"Clicking element [{el_id}]"}
                                # Handle HTML <select> dropdowns natively in Playwright
                                if tag_name == 'select':
                                    element_handle.select_option(label=action_val)
                                else:
                                    try:
                                        element_handle.click(timeout=1500)
                                    except Exception as e1:
                                        # Fallback 1: Force click (ignoring overlap checks)
                                        try:
                                            element_handle.click(force=True, timeout=1000)
                                        except Exception as e2:
                                            # Fallback 2: Javascript click trigger
                                            try:
                                                page.evaluate("el => el.click()", element_handle)
                                            except Exception as e3:
                                                # Fallback 3: Click closest <label> or parent wrapper
                                                try:
                                                    parent_handle = page.evaluate_handle("el => el.closest('label') || el.parentElement", element_handle)
                                                    if parent_handle:
                                                        parent_handle.click(force=True, timeout=1000)
                                                except Exception:
                                                    raise Exception(f"All click strategies failed. Standard: {str(e1)}, Force: {str(e2)}, JS: {str(e3)}")
                                    
                            page.wait_for_timeout(5000) # 5 seconds delay between actions to avoid rate limits
                        except Exception as e:
                            yield {"status": "warning", "message": f"Failed to execute action on element [{el_id}]: {str(e)}"}

                # Capture post-fill screenshot for UI representation
                post_screenshot_bytes = page.screenshot(type="png", full_page=False)
                yield {
                    "status": "step_end",
                    "step": step_count,
                    "screenshot": post_screenshot_bytes
                }

                # Execute navigation action (Next/Submit) if specified
                nav_id = ai_response.navigation_action_id
                if nav_id is not None:
                    yield {"status": "info", "message": f"Clicking navigation button [{nav_id}]..."}
                    try:
                        nav_handle = page.evaluate_handle(f"window.surveyElements[{nav_id - 1}]")
                        try:
                            nav_handle.click(timeout=1500)
                        except Exception:
                            try:
                                nav_handle.click(force=True, timeout=1000)
                            except Exception:
                                page.evaluate("el => el.click()", nav_handle)
                        
                        # Wait for page load/navigation to finish
                        yield {"status": "info", "message": "Waiting for next page or submit confirmation..."}
                        page.wait_for_timeout(5000) # wait for page change and rate limit avoidance
                    except Exception as e:
                        yield {"status": "warning", "message": f"Failed to click navigation button [{nav_id}]: {str(e)}"}
                        # Wait anyway
                        page.wait_for_timeout(2000)
                else:
                    # If AI did not select a navigation button but did fill fields, maybe it expects to scroll or submit later,
                    # or it thinks it's done. If it performed no actions and no navigation, we assume it's done or stuck.
                    if not ai_response.actions:
                        yield {"status": "info", "message": "No actions taken. Ending loop."}
                        # Capture confirmation
                        body_text = page.inner_text("body").lower()
                        completion_keywords = ["recorded", "thank you", "submitted", "done", "response", "completed", "success"]
                        is_completed = any(kw in body_text for kw in completion_keywords)
                        if is_completed:
                            yield {
                                "status": "success",
                                "message": "Survey completed! Confirmation page detected.",
                                "screenshot": post_screenshot_bytes
                            }
                        else:
                            yield {
                                "status": "success",
                                "message": "Survey filler finished (no further actions suggested by AI).",
                                "screenshot": post_screenshot_bytes
                            }
                        break
                    
                    # Give a small wait
                    page.wait_for_timeout(1000)

            else:
                # Max steps exceeded
                yield {"status": "error", "message": "Reached maximum limit of 10 pages/steps."}
                
        except Exception as e:
            yield {"status": "error", "message": f"An unexpected error occurred during execution: {str(e)}"}
        finally:
            yield {"status": "info", "message": "Closing browser..."}
            try:
                browser.close()
            except:
                pass
            yield {"status": "finished"}
