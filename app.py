import streamlit as st
import os
import time
from dotenv import load_dotenv
from survey_agent import run_survey_filler

# Load environment variables (useful for local development)
load_dotenv()

# Streamlit Page Setup
st.set_page_config(
    page_title="AI Survey Mimic Bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Inter:wght@300;400;500;600&display=swap');
    
    /* Global Styles */
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3, .title-text {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Gradient Headers */
    .app-header {
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.8rem;
        margin-bottom: 0.2rem;
        text-align: left;
    }
    
    .app-subtitle {
        color: #8a99ad;
        font-size: 1.1rem;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    
    /* Glassmorphism Cards */
    .custom-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.8rem;
        margin-bottom: 1.5rem;
        backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
    }
    
    .card-title {
        color: #ffffff;
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Reasoning Box */
    .reasoning-box {
        background: rgba(168, 85, 247, 0.08);
        border-left: 4px solid #a855f7;
        padding: 1.2rem;
        border-radius: 4px 12px 12px 4px;
        margin-bottom: 1.5rem;
        color: #e2e8f0;
    }
    
    .reasoning-title {
        font-weight: 600;
        color: #c084fc;
        margin-bottom: 0.4rem;
        font-size: 0.95rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Log Output Box */
    .console-log {
        background-color: #0b0f19;
        font-family: 'Courier New', Courier, monospace;
        color: #38bdf8;
        padding: 1.2rem;
        border-radius: 10px;
        border: 1px solid #1e293b;
        max-height: 300px;
        overflow-y: auto;
        font-size: 0.85rem;
        margin-top: 1rem;
        line-height: 1.5;
        box-shadow: inset 0 2px 8px rgba(0,0,0,0.8);
    }
    
    .log-entry {
        margin-bottom: 4px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.02);
        padding-bottom: 4px;
    }
    
    .log-info { color: #38bdf8; }
    .log-warning { color: #f59e0b; }
    .log-error { color: #ef4444; }
    .log-success { color: #10b981; }

    /* Buttons styling */
    div.stButton > button {
        background: linear-gradient(90deg, #6366f1 0%, #a855f7 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.6rem 2rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4) !important;
    }
    
    div.stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(168, 85, 247, 0.6) !important;
    }
    
    /* Preset quick buttons */
    .preset-btn {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.8rem;
        color: #cbd5e1;
        cursor: pointer;
        display: inline-block;
        margin: 4px;
        transition: all 0.2s ease;
    }
    .preset-btn:hover {
        background-color: #334155;
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# App Header
st.markdown('<div class="app-header">🤖 AI Survey Persona Mimic</div>', unsafe_allow_html=True)
st.markdown('<div class="app-subtitle">Feed a survey form link, describe a persona, and let the AI fill it automatically.</div>', unsafe_allow_html=True)

# API Key Check
env_api_key = os.environ.get("GEMINI_API_KEY", "")

# Sidebar Configuration
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    
    # API Key management
    if env_api_key:
        api_key = st.text_input("Gemini API Key", value=env_api_key, type="password", help="Loaded from environment variables.")
    else:
        api_key = st.text_input("Gemini API Key", type="password", help="Get a key from Google AI Studio.")
        
    st.markdown("---")
    

    
    # Browser Run Mode Settings
    run_mode = st.toggle("Headed Mode", value=False, help="Run browser with visible window. Note: Chrome will open on the host machine.")
    
    # Max pages / steps
    max_steps = st.number_input(
        "Max Pages / Steps",
        min_value=5,
        max_value=150,
        value=30,
        step=5,
        help="Safety cap: the bot will stop after running this many steps or pages to prevent infinite loops."
    )
    
    st.markdown("""
    ### ℹ️ About
    This bot uses **Playwright** to load the target survey page and run a visual annotation script (similar to Vimium/browser-use) which overlays numbered badges on each form input.
    
    **Gemini 2.5 Flash** then looks at a screenshot of the annotated page and element labels to fill it out precisely according to the target persona.
    """)

# Define Persona Presets
presets = {
    "Teenage Gamer 🎮": "A tech-savvy 16-year-old high school student who loves multiplayer gaming, speaks in Gen-Z internet slang (like 'fr', 'no cap', 'bet', 'hype'), hates homework, and is highly energetic.",
    "Skeptical Tax Auditor 📊": "A meticulous, highly detailed, and formal 62-year-old retired IRS tax auditor. Skeptical of marketing jargon, values exact numbers and structural organization, and writes in clean, formal language.",
    "Eco-Conscious Enthusiast 🌱": "A passionate 28-year-old vegan climate advocate who works at an environmental NGO. Always prefers sustainable choices, hates single-use plastics, is extremely optimistic but concerned about the planet.",
    "Busy Stressed Developer 💻": "A senior software engineer under tight deadlines. Stressed, direct, wants to get straight to the point, answers briefly, dislikes unnecessary questions, and values efficiency above all."
}

# Main Application Layout
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📝 Survey Configuration</div>', unsafe_allow_html=True)
    
    survey_url = st.text_input(
        "Survey Form URL", 
        placeholder="https://docs.google.com/forms/d/e/.../viewform",
        help="Paste a Google Forms, Microsoft Forms, or standard HTML survey form link here."
    )
    
    st.markdown("##### Select a Preset Persona or Write Your Own:")
    preset_cols = st.columns(4)
    selected_preset = None
    for idx, (label, text) in enumerate(presets.items()):
        if preset_cols[idx % 4].button(label, key=f"btn_{idx}"):
            st.session_state["bot_persona"] = text
            
    persona_desc = st.text_area(
        "Bot Persona Description",
        key="bot_persona",
        placeholder="Describe the demographic, background, attitude, and tone of the person the bot should mimic...",
        height=180,
        help="Specify age, profession, preferences, tone, or specific opinions the bot should hold."
    )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Run controls
    if not api_key:
        st.warning("⚠️ Please provide a Google Gemini API Key in the sidebar settings to start.")
        run_disabled = True
    elif not survey_url:
        run_disabled = True
    else:
        run_disabled = False
        
    start_btn = st.button("🚀 Start Survey Bot", disabled=run_disabled)

with col_right:
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🔍 Live Execution Dashboard</div>', unsafe_allow_html=True)
    
    # Placeholder for status and progress
    status_placeholder = st.empty()
    
    # Placeholder for Gemini Reasoning
    reasoning_placeholder = st.empty()
    
    # Placeholder for Screen Preview
    preview_placeholder = st.empty()
    
    # Logs layout
    st.write("##### 📄 System Logs")
    logs_placeholder = st.empty()
    
    st.markdown('</div>', unsafe_allow_html=True)

# Run process
if start_btn:
    logs = []
    
    def log_message(msg, type="info"):
        timestamp = time.strftime("%H:%M:%S")
        color_class = f"log-{type}"
        logs.append(f'<div class="log-entry"><span style="color:#64748b;">[{timestamp}]</span> <span class="{color_class}">{msg}</span></div>')
        # Render logs in reverse order so newest is at top, or standard
        logs_placeholder.markdown(f'<div class="console-log">{"".join(logs[::-1])}</div>', unsafe_allow_html=True)

    log_message("Starting survey filler process...", "info")
    status_placeholder.info("Initializing Playwright and loading page...")
    
    # Start generator
    agent_generator = run_survey_filler(
        url=survey_url,
        persona=persona_desc,
        api_key=api_key,
        model_name="gemma-4-31b-it",
        max_steps=max_steps,
        headless=not run_mode
    )
    
    last_screenshot = None
    
    for step_data in agent_generator:
        status_type = step_data.get("status")
        
        if status_type == "info":
            msg = step_data.get("message")
            log_message(msg, "info")
            status_placeholder.info(msg)
            
        elif status_type == "warning":
            msg = step_data.get("message")
            log_message(msg, "warning")
            
        elif status_type == "error":
            msg = step_data.get("message")
            log_message(msg, "error")
            status_placeholder.error(msg)
            if "screenshot" in step_data:
                preview_placeholder.image(step_data["screenshot"], caption="Error State Screenshot", width="stretch")
                
        elif status_type == "step_start":
            step = step_data.get("step")
            screenshot = step_data.get("screenshot")
            elements = step_data.get("elements")
            log_message(f"Step {step}: Elements annotated. Total fields: {len(elements)}", "info")
            status_placeholder.warning(f"Step {step}: Form annotated. AI analyzing answers...")
            preview_placeholder.image(screenshot, caption=f"Step {step} - Annotated Page (Red Badges)", width="stretch")
            
        elif status_type == "ai_response":
            reasoning = step_data.get("reasoning")
            actions = step_data.get("actions")
            nav_id = step_data.get("navigation_action_id")
            
            # Render Reasoning
            reasoning_placeholder.markdown(f"""
            <div class="reasoning-box">
                <div class="reasoning-title">🧠 AI Reasoning / Persona Alignment</div>
                <div>{reasoning}</div>
            </div>
            """, unsafe_allow_html=True)
            
            log_message(f"AI Reasoning: {reasoning}", "info")
            log_message(f"AI planned {len(actions)} filling actions. Next/Submit Button ID: {nav_id}", "info")
            
        elif status_type == "step_end":
            step = step_data.get("step")
            screenshot = step_data.get("screenshot")
            status_placeholder.success(f"Step {step}: Fields filled successfully!")
            preview_placeholder.image(screenshot, caption=f"Step {step} - Post-Fill State", width="stretch")
            
        elif status_type == "success":
            msg = step_data.get("message")
            log_message(msg, "success")
            status_placeholder.success(f"🎉 Success: {msg}")
            if "screenshot" in step_data:
                preview_placeholder.image(step_data["screenshot"], caption="Confirmation Screen", width="stretch")
                
        elif status_type == "finished":
            log_message("Survey session ended.", "success")
            # Clear running status after a brief delay
            time.sleep(1)
