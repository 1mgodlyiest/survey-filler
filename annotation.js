/**
 * survey_annotation.js
 * Injected into the survey webpage using Playwright.
 * It identifies interactive elements, labels them visually,
 * and extracts their metadata.
 */
(function() {
    // 1. Clean up any previous annotations
    const existingContainer = document.getElementById('antigravity-annotation-container');
    if (existingContainer) {
        existingContainer.remove();
    }
    
    // Store elements globally to interact with them later
    window.surveyElements = [];
    
    // Create container for overlay badges
    const container = document.createElement('div');
    container.id = 'antigravity-annotation-container';
    container.style.position = 'absolute';
    container.style.top = '0';
    container.style.left = '0';
    container.style.width = '100%';
    container.style.height = '100%';
    container.style.pointerEvents = 'none';
    container.style.zIndex = '9999999';
    document.body.appendChild(container);

    // Helpers to find labels
    function getCleanText(text) {
        if (!text) return '';
        return text.replace(/\s+/g, ' ').trim();
    }

    function findLabelForElement(el) {
        // A. Check for standard aria-label or placeholder
        if (el.getAttribute('aria-label')) {
            return getCleanText(el.getAttribute('aria-label'));
        }
        if (el.getAttribute('placeholder')) {
            return getCleanText(el.getAttribute('placeholder'));
        }

        // B. Check for aria-labelledby
        const labelledBy = el.getAttribute('aria-labelledby');
        if (labelledBy) {
            const labelEl = document.getElementById(labelledBy);
            if (labelEl && labelEl.textContent) {
                return getCleanText(labelEl.textContent);
            }
        }

        // C. Check associated HTML <label>
        if (el.id) {
            const labelEl = document.querySelector(`label[for="${el.id}"]`);
            if (labelEl && labelEl.textContent) {
                return getCleanText(labelEl.textContent);
            }
        }

        // D. Google Forms specific question text traversal
        // Google Forms questions are usually in a container that has role="listitem"
        // and contain a div with class like "hoXoCc" or "geS5ne" or question title.
        let parentListItem = el.closest('[role="listitem"]');
        if (parentListItem) {
            // Find the question header
            // Typically Google Forms question text is in the first child structure of role="listitem"
            const firstHeader = parentListItem.querySelector('[role="heading"], .geS5ne, .hoXoCc');
            if (firstHeader && firstHeader.textContent) {
                return getCleanText(firstHeader.textContent);
            }
        }

        // E. General traversal up the DOM to find some label-like container
        let current = el.parentElement;
        for (let i = 0; i < 4; i++) {
            if (!current) break;
            // Check if there is text in the sibling or parent
            const textContent = current.innerText || current.textContent;
            if (textContent && textContent.length > 2 && textContent.length < 300) {
                // If it's a common container, try to search for header classes
                const possibleHeader = current.querySelector('h1, h2, h3, h4, [role="heading"]');
                if (possibleHeader && possibleHeader.textContent) {
                    return getCleanText(possibleHeader.textContent);
                }
            }
            current = current.parentElement;
        }

        // F. Last resort: name attribute
        if (el.name) {
            return el.name;
        }

        return '';
    }

    // Find all potential interactive elements
    const elementsToTag = [];
    
    // Select standard form controls
    const selectors = [
        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="image"])',
        'textarea',
        'select',
        'button',
        '[role="radio"]',
        '[role="checkbox"]',
        '[role="button"]',
        '[role="listbox"]',
        '[role="option"]'
    ];
    
    const candidateNodes = document.querySelectorAll(selectors.join(','));

    candidateNodes.forEach(node => {
        // Basic visibility check
        const rect = node.getBoundingClientRect();
        const style = window.getComputedStyle(node);
        
        const isVisible = rect.width > 0 && 
                          rect.height > 0 && 
                          style.display !== 'none' && 
                          style.visibility !== 'hidden';
                          
        if (!isVisible) return;
        
        // Exclude elements that are nested in others that we've already tagged if they are identical
        // or exclude elements inside an ignored parent (e.g. annotations themselves)
        if (node.closest('#antigravity-annotation-container')) return;

        // Skip certain buttons that are just wrapper icons
        if (node.tagName === 'BUTTON' && node.textContent.trim() === '' && !node.getAttribute('aria-label')) {
            // Might still be a functional icon button, but let's look at parents
        }

        elementsToTag.push(node);
    });

    // Annotate and create metadata list
    const metadataList = [];
    let idCounter = 1;

    elementsToTag.forEach(el => {
        const rect = el.getBoundingClientRect();
        
        // Adjust for page scroll
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
        
        const absoluteTop = rect.top + scrollTop;
        const absoluteLeft = rect.left + scrollLeft;
        
        // Check if there's already a very close tag to avoid overlap (e.g. radio button inside label or custom radio container)
        // Some libraries use nested role="radio" and input[type="radio"]. We should avoid tagging both.
        let isDuplicate = false;
        for (let i = 0; i < window.surveyElements.length; i++) {
            const existingRect = window.surveyElements[i].getBoundingClientRect();
            const dist = Math.hypot(rect.left - existingRect.left, rect.top - existingRect.top);
            // If they are practically at the same location, keep the more specific custom element or skip duplicate
            if (dist < 15) {
                isDuplicate = true;
                break;
            }
        }
        if (isDuplicate) return;

        const id = idCounter++;
        window.surveyElements.push(el);

        // Determine subtype and properties
        let tagType = el.tagName.toLowerCase();
        let elType = el.getAttribute('type') || '';
        let role = el.getAttribute('role') || '';
        
        let typeStr = 'text'; // default
        if (tagType === 'textarea') {
            typeStr = 'textarea';
        } else if (tagType === 'select') {
            typeStr = 'dropdown';
        } else if (role === 'radio' || elType === 'radio') {
            typeStr = 'radio';
        } else if (role === 'checkbox' || elType === 'checkbox') {
            typeStr = 'checkbox';
        } else if (role === 'button' || tagType === 'button' || elType === 'button' || elType === 'submit') {
            typeStr = 'button';
        } else if (role === 'listbox') {
            typeStr = 'dropdown';
        } else if (elType === 'number') {
            typeStr = 'number';
        } else if (elType === 'date') {
            typeStr = 'date';
        }

        // Get label text
        let rawLabel = findLabelForElement(el);
        // If it's a radio option, check if there's text inside or right next to it
        let optionText = '';
        if (typeStr === 'radio' || typeStr === 'checkbox') {
            optionText = getCleanText(el.textContent || el.innerText);
            // If option text is empty, search siblings
            if (!optionText && el.parentElement) {
                optionText = getCleanText(el.parentElement.textContent || el.parentElement.innerText);
                // Clean option text by removing the main label if it got concatenated
                if (rawLabel && optionText.includes(rawLabel)) {
                    optionText = getCleanText(optionText.replace(rawLabel, ''));
                }
            }
        }

        // Create overlay badge
        const badge = document.createElement('div');
        badge.className = 'antigravity-badge';
        badge.style.position = 'absolute';
        badge.style.top = `${absoluteTop}px`;
        badge.style.left = `${absoluteLeft}px`;
        badge.style.backgroundColor = '#ff3b30'; // red
        badge.style.color = '#ffffff';
        badge.style.fontSize = '11px';
        badge.style.fontWeight = 'bold';
        badge.style.padding = '2px 5px';
        badge.style.borderRadius = '3px';
        badge.style.border = '1px solid white';
        badge.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';
        badge.style.zIndex = '9999999';
        badge.style.pointerEvents = 'none';
        badge.textContent = id;
        container.appendChild(badge);

        // Highlight element border briefly or subtly
        // Store original border to restore if needed, or just let it overlay
        
        metadataList.push({
            id: id,
            type: typeStr,
            tag: tagType,
            role: role,
            name: el.getAttribute('name') || '',
            label: rawLabel,
            option_text: optionText,
            value: el.value || '',
            checked: el.checked || el.getAttribute('aria-checked') === 'true'
        });
    });

    return metadataList;
})();
