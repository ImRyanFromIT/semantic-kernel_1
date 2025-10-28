document.addEventListener('DOMContentLoaded', () => {

    // --- DATA ---
    const i18n = {
        en: {
            problemLabel: "Describe your problem or lookup a hostname",
            helperText: "For SRM: describe your problem. For hostname: use 'lookup:' prefix.",
            search: "Search",
            searching: "Searching...",
            searchingMessage: "Searching for the right SRM...",
            searchingHostnameMessage: "Looking up hostname information...",
            suggestions: [
                "Expand storage on a file share",
                "Restore deleted files",
                "Add more CPU to a VM",
                "lookup: srv-vmcap-001-prod",
                "lookup: aiopsdi"
            ],
            resultFound: "1 result found.",
            firstResult: "The result is",
            hostnameFound: "Hostname information found.",
            noResultsTitle: "No matching Connector found",
            noResultsBody: "Your request will be routed to a general queue. Please submit it and a team member will assist you.",
            connectionError: "Connection Error",
            connectionErrorBody: "Unable to connect to the server. Please try again later.",
            language: "Language:",
            themeSystem: "System",
            themeLight: "Light",
            themeDark: "Dark"
        },
        es: {
            problemLabel: "Describa su problema o busque un hostname",
            helperText: "Para SRM: describa su problema. Para hostname: use el prefijo 'lookup:'.",
            search: "Buscar",
            searching: "Buscando...",
            searchingMessage: "Buscando el SRM correcto...",
            searchingHostnameMessage: "Buscando información del hostname...",
            suggestions: [
                "Ampliar almacenamiento",
                "Restaurar archivos",
                "Añadir más CPU a una VM",
                "lookup: srv-vmcap-001-prod",
                "lookup: aiopsdi"
            ],
            resultFound: "1 resultado encontrado.",
            firstResult: "El resultado es",
            hostnameFound: "Información del hostname encontrada.",
            noResultsTitle: "No se encontró ningún Conector coincidente",
            noResultsBody: "Su solicitud se enviará a una cola general. Envíela y un miembro del equipo le ayudará.",
            connectionError: "Error de conexión",
            connectionErrorBody: "No se puede conectar al servidor. Inténtelo de nuevo más tarde.",
            language: "Idioma:",
            themeSystem: "Sistema",
            themeLight: "Claro",
            themeDark: "Oscuro"
        }
    };
    let currentLocale = 'en';

    // --- DOM ELEMENTS ---
    const form = document.getElementById('srm-search-form');
    const input = document.getElementById('problem-description');
    const searchBtn = document.getElementById('search-btn');
    const resultsContainer = document.getElementById('results-container');
    const suggestionContainer = document.getElementById('suggestion-buttons-container');
    const srAnnouncer = document.getElementById('sr-announcer');
    const localeSwitcher = document.getElementById('locale-switcher');
    const themeRadios = document.querySelectorAll('input[name="theme"]');
    const mainContent = document.getElementById('main-content');
    const finderWrapper = document.querySelector('.srm-finder-wrapper');

    // --- FUNCTIONS ---

    const sanitize = (str) => {
        const temp = document.createElement('div');
        temp.textContent = str;
        return temp.innerHTML;
    };
    
    const callBackend = async (endpoint, payload) => {
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            return data.response;
        } catch (error) {
            console.error('Backend error:', error);
            throw error;
        }
    };
    
    const realBackendSearch = async (query) => callBackend('/api/query', { query });
    const realBackendHostnameSearch = async (hostname) => callBackend('/api/hostname', { hostname });
    
    const parseMarkdownResponse = (markdown) => {
        // Handle special response types
        if (markdown.startsWith('[!]')) {
            return { type: 'error', message: markdown.substring(3).trim() };
        }
        if (markdown.startsWith('[?]')) {
            return { type: 'clarification', message: markdown.substring(3).trim() };
        }
        
        // Parse recommended SRM
        const nameMatch = markdown.match(/##\s+Recommended SRM:\s+(.+)/);
        const srmIdMatch = markdown.match(/\*\*SRM ID:\*\*\s+(.+)/);
        const categoryMatch = markdown.match(/\*\*Category:\*\*\s+(.+)/);
        const useCaseMatch = markdown.match(/\*\*Use Case:\*\*\s+(.+)/);
        const owningTeamMatch = markdown.match(/\*\*Owning Team:\*\*\s+(.+)/);
        const urlMatch = markdown.match(/\*\*URL:\*\*\s+(.+)/);
        const ownerNotesMatch = markdown.match(/\*\*Owner Notes:\*\*\s+(.+?)(?=\n\*\*|\n###|$)/s);
        const hiddenNotesMatch = markdown.match(/\*\*Hidden Notes:\*\*\s+(.+?)(?=\n\*\*|\n###|$)/s);
        
        if (!nameMatch) {
            // No matching SRM found
            return { type: 'no_results', message: markdown };
        }
        
        const result = {
            type: 'success',
            name: nameMatch[1].trim(),
            srmId: srmIdMatch ? srmIdMatch[1].trim() : null,
            category: categoryMatch ? categoryMatch[1].trim() : '',
            useCase: useCaseMatch ? useCaseMatch[1].trim() : '',
            owningTeam: owningTeamMatch ? owningTeamMatch[1].trim() : '',
            url: urlMatch ? urlMatch[1].trim() : '',
            ownerNotes: ownerNotesMatch ? ownerNotesMatch[1].trim() : '',
            hiddenNotes: hiddenNotesMatch ? hiddenNotesMatch[1].trim() : '',
            alternatives: []
        };
        
        // Parse alternatives section
        const alternativesSection = markdown.split('### Alternative Options:')[1];
        if (alternativesSection) {
            const altLines = alternativesSection.split('\n');
            let currentAlt = null;
            
            for (const line of altLines) {
                // Match numbered alternatives: "1. **Name** (ID: SRM-XXX, Category) - Use case"
                const altMatch = line.match(/^\d+\.\s+\*\*(.+?)\*\*\s+\(ID:\s+(.+?),\s+(.+?)\)\s+-\s+(.+)/);
                if (altMatch) {
                    if (currentAlt) {
                        result.alternatives.push(currentAlt);
                    }
                    currentAlt = {
                        name: altMatch[1].trim(),
                        srmId: altMatch[2].trim(),
                        category: altMatch[3].trim(),
                        useCase: altMatch[4].trim(),
                        url: ''
                    };
                } else if (currentAlt && line.includes('**URL:**')) {
                    const urlMatch = line.match(/\*\*URL:\*\*\s+(.+)/);
                    if (urlMatch) {
                        currentAlt.url = urlMatch[1].trim();
                    }
                }
            }
            
            if (currentAlt) {
                result.alternatives.push(currentAlt);
            }
        }
        
        return result;
    };
    
    const parseHostnameResponse = (markdown) => {
        // Handle special response types
        if (markdown.startsWith('[!]')) {
            return { type: 'error', message: markdown.substring(3).trim() };
        }
        
        // Check if it's a single hostname match
        if (markdown.includes('## Hostname Details')) {
            const hostnameMatch = markdown.match(/\*\*Hostname:\*\*\s+(.+)/);
            const applicationMatch = markdown.match(/\*\*Application:\*\*\s+(.+)/);
            const maintenanceMatch = markdown.match(/\*\*Maintenance Window:\*\*\s+(.+)/);
            const teamMatch = markdown.match(/\*\*Team:\*\*\s+(.+)/);
            const contactMatch = markdown.match(/\*\*Contact:\*\*\s+(.+)/);
            
            if (hostnameMatch) {
                return {
                    type: 'hostname_success',
                    hostname: hostnameMatch[1].trim(),
                    application: applicationMatch ? applicationMatch[1].trim() : '',
                    maintenanceWindow: maintenanceMatch ? maintenanceMatch[1].trim() : '',
                    team: teamMatch ? teamMatch[1].trim() : '',
                    contact: contactMatch ? contactMatch[1].trim() : ''
                };
            }
        }
        
        // Check for multiple matches
        if (markdown.includes('Multiple matches found')) {
            return { type: 'hostname_multiple', message: markdown };
        }
        
        // Check for no match
        if (markdown.includes('No hostname found')) {
            return { type: 'hostname_not_found', message: markdown };
        }
        
        // Default: treat as plain message
        return { type: 'hostname_info', message: markdown };
    };

    // Store current session and query for feedback
    let currentSession = {
        sessionId: null,
        query: null,
        selectedSrm: null,
        alternatives: []
    };
    
    const renderResults = (parsedResult) => {
        resultsContainer.innerHTML = '';
        
        // Handle error/clarification/no results
        if (!parsedResult || parsedResult.type === 'no_results') {
            resultsContainer.innerHTML = `
                <div class="empty-state" data-testid="empty-state">
                    <h3>${i18n[currentLocale].noResultsTitle}</h3>
                    <p>${i18n[currentLocale].noResultsBody}</p>
                </div>
            `;
            return;
        }
        
        if (parsedResult.type === 'error') {
            resultsContainer.innerHTML = `
                <div class="empty-state" data-testid="error-state">
                    <h3>Error</h3>
                    <p>${sanitize(parsedResult.message)}</p>
                </div>
            `;
            return;
        }
        
        if (parsedResult.type === 'clarification') {
            resultsContainer.innerHTML = `
                <div class="empty-state" data-testid="clarification-state">
                    <h3>Need More Information</h3>
                    <p>${sanitize(parsedResult.message)}</p>
                </div>
            `;
            return;
        }

        // Render successful SRM result
        const resultCountText = document.createElement('h2');
        resultCountText.className = 'visually-hidden';
        resultCountText.textContent = i18n[currentLocale].resultFound;
        resultsContainer.appendChild(resultCountText);
        
        const list = document.createElement('ul');
        list.className = 'results-list';
        list.setAttribute('role', 'list');
        
        const listItem = document.createElement('li');
        listItem.className = 'srm-card';
        listItem.setAttribute('role', 'listitem');
        listItem.setAttribute('data-testid', 'srm-card-result');
        
        let cardContent = `<h2 data-testid="srm-name">${sanitize(parsedResult.name)}</h2>`;
        
        // Add category
        if (parsedResult.category) {
            cardContent += `
                <div class="srm-field">
                    <span class="srm-field-label">Category:</span>
                    <span class="srm-field-value">${sanitize(parsedResult.category)}</span>
                </div>
            `;
        }
        
        // Add use case
        if (parsedResult.useCase) {
            cardContent += `
                <div class="srm-field">
                    <span class="srm-field-label">Use Case:</span>
                    <span class="srm-field-value">${sanitize(parsedResult.useCase)}</span>
                </div>
            `;
        }
        
        // Add owning team
        if (parsedResult.owningTeam) {
            cardContent += `
                <div class="srm-field">
                    <span class="srm-field-label">Owning Team:</span>
                    <span class="srm-field-value">${sanitize(parsedResult.owningTeam)}</span>
                </div>
            `;
        }
        
        // Add URL
        if (parsedResult.url) {
            cardContent += `
                <div class="srm-field">
                    <span class="srm-field-label">URL:</span>
                    <a href="${sanitize(parsedResult.url)}" class="srm-url" target="_blank" rel="noopener noreferrer">${sanitize(parsedResult.url)}</a>
                </div>
            `;
        }
        
        // Add Owner Notes
        if (parsedResult.ownerNotes) {
            cardContent += `
                <div class="srm-field srm-notes-field">
                    <span class="srm-field-label">Owner Notes:</span>
                    <div class="srm-notes-content">${sanitize(parsedResult.ownerNotes)}</div>
                </div>
            `;
        }
        
        // Add Hidden Notes (only show if present - these are internal)
        if (parsedResult.hiddenNotes) {
            cardContent += `
                <div class="srm-field srm-notes-field">
                    <span class="srm-field-label">Hidden Notes:</span>
                    <div class="srm-notes-content srm-hidden-notes">${sanitize(parsedResult.hiddenNotes)}</div>
                </div>
            `;
        }
        
        // Render up to two alternative options (if any)
        if (parsedResult.alternatives && parsedResult.alternatives.length > 0) {
            const maxAlts = Math.min(2, parsedResult.alternatives.length);
            let altHtml = '';
            for (let i = 0; i < maxAlts; i++) {
                const alt = parsedResult.alternatives[i];
                const altCategory = alt.category ? sanitize(alt.category) : '';
                const altUseCase = alt.useCase ? sanitize(alt.useCase) : '';
                const altUrl = alt.url ? sanitize(alt.url) : '';
                
                altHtml += `
                    <li class="alt-item">
                        <div class="alt-name">${sanitize(alt.name || '')}</div>
                        ${altCategory ? `<div class="alt-meta"><span class="alt-label">Category:</span> ${altCategory}</div>` : ''}
                        ${altUseCase ? `<div class="alt-meta"><span class="alt-label">Use Case:</span> ${altUseCase}</div>` : ''}
                        ${altUrl ? `<div class="alt-meta"><span class="alt-label">URL:</span> <a href="${altUrl}" target="_blank" rel="noopener noreferrer">${altUrl}</a></div>` : ''}
                    </li>
                `;
            }
            cardContent += `
                <div class="srm-alternatives">
                    <h3>Alternative Options</h3>
                    <ol class="alt-list">
                        ${altHtml}
                    </ol>
                </div>
            `;
        }
        
        // Add feedback buttons
        cardContent += `
            <div class="feedback-buttons">
                <button class="feedback-btn feedback-positive" data-action="positive">
                    <span class="feedback-icon">👍</span> This is correct
                </button>
                <button class="feedback-btn feedback-negative" data-action="negative">
                    <span class="feedback-icon">👎</span> Not quite right
                </button>
            </div>
        `;
        
        // Add footer note
        cardContent += `<p class="srm-footer">If this doesn't match your need, please provide more details and I'll search again.</p>`;
        
        listItem.innerHTML = cardContent;
        list.appendChild(listItem);
        resultsContainer.appendChild(list);

        announce(`${i18n[currentLocale].firstResult} ${parsedResult.name}.`);
    };
    
    const renderEmptyState = (title, message, testId = 'empty-state') => {
        resultsContainer.innerHTML = `
            <div class="empty-state" data-testid="${testId}">
                ${title ? `<h3>${title}</h3>` : ''}
                <p>${sanitize(message).replace(/\n/g, '<br>')}</p>
            </div>
        `;
    };
    
    const announce = (message) => {
        srAnnouncer.textContent = message;
        setTimeout(() => srAnnouncer.textContent = '', 1000);
    };
    
    const renderField = (label, value, cssClass = 'hostname') => {
        if (!value) return '';
        return `
            <div class="${cssClass}-field">
                <span class="${cssClass}-field-label">${label}:</span>
                <span class="${cssClass}-field-value">${sanitize(value)}</span>
            </div>
        `;
    };
    
    const renderHostnameResults = (parsedResult) => {
        resultsContainer.innerHTML = '';
        
        // Handle error states
        if (parsedResult.type === 'error') {
            return renderEmptyState('Error', parsedResult.message, 'error-state');
        }
        
        // Handle info/multiple/not found states
        if (['hostname_multiple', 'hostname_not_found', 'hostname_info'].includes(parsedResult.type)) {
            return renderEmptyState('', parsedResult.message, 'hostname-info-state');
        }
        
        // Render successful hostname result
        const fields = [
            { label: 'Application', value: parsedResult.application },
            { label: 'Maintenance Window', value: parsedResult.maintenanceWindow },
            { label: 'Team', value: parsedResult.team },
            { label: 'Contact', value: parsedResult.contact }
        ];
        
        const cardContent = `
            <h2 data-testid="hostname-name">${sanitize(parsedResult.hostname)}</h2>
            ${fields.map(f => renderField(f.label, f.value)).join('')}
            <p class="hostname-footer">For questions about this system, contact the team listed above.</p>
        `;
        
        resultsContainer.innerHTML = `
            <h2 class="visually-hidden">${i18n[currentLocale].hostnameFound}</h2>
            <ul class="results-list" role="list">
                <li class="hostname-card" role="listitem" data-testid="hostname-card-result">
                    ${cardContent}
                </li>
            </ul>
        `;

        announce(`${i18n[currentLocale].hostnameFound} ${parsedResult.hostname}.`);
    };
    
    const updateUIStrings = () => {
        document.documentElement.lang = currentLocale;
        document.getElementById('problem-label').textContent = i18n[currentLocale].problemLabel;
        document.getElementById('problem-description').placeholder = "e.g., 'Restore backup from yesterday'";
        document.getElementById('helper-text').textContent = i18n[currentLocale].helperText;
        document.getElementById('search-btn').textContent = i18n[currentLocale].search;
        document.getElementById('locale-label').textContent = i18n[currentLocale].language;
        document.querySelector('label[for="theme-system"]').textContent = i18n[currentLocale].themeSystem;
        document.querySelector('label[for="theme-light"]').textContent = i18n[currentLocale].themeLight;
        document.querySelector('label[for="theme-dark"]').textContent = i18n[currentLocale].themeDark;
        
        suggestionContainer.innerHTML = '';
        i18n[currentLocale].suggestions.forEach(text => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'suggestion-btn';
            button.textContent = text;
            suggestionContainer.appendChild(button);
        });
    };

    const handleThemeChange = (theme) => {
        if (theme === 'system') {
            document.documentElement.removeAttribute('data-theme');
            localStorage.removeItem('theme');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('theme', theme);
        }
    };

    const detectQueryType = (query) => {
        const lowerQuery = query.toLowerCase();
        const prefix = 'lookup:';
        const prefixLength = 7;
        
        if (lowerQuery.startsWith(prefix)) {
            return { isHostname: true, query: query.substring(prefixLength).trim() };
        }
        return { isHostname: false, query: query.trim() };
    };
    
    const setLoadingState = (isLoading, isHostname = false) => {
        searchBtn.setAttribute('aria-busy', isLoading);
        resultsContainer.setAttribute('aria-busy', isLoading);
        searchBtn.disabled = isLoading;
        searchBtn.textContent = isLoading ? i18n[currentLocale].searching : i18n[currentLocale].search;
        searchBtn.classList.toggle('searching', isLoading);
        
        if (isLoading) {
            const message = isHostname ? 
                i18n[currentLocale].searchingHostnameMessage : 
                i18n[currentLocale].searchingMessage;
            
            resultsContainer.innerHTML = `
                <div class="loading-state" data-testid="loading-state">
                    <div class="spinner"></div>
                    <p>${message}</p>
                </div>
            `;
        }
    };
    
    const runSearch = async (query) => {
        if (!query.trim()) return;

        const { isHostname, query: processedQuery } = detectQueryType(query);
        const originalButtonText = searchBtn.textContent;
        
        setLoadingState(true, isHostname);
        
        try {
            const response = await fetch(isHostname ? '/api/hostname' : '/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(isHostname ? { hostname: processedQuery } : { query })
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            const markdown = data.response;
            
            // Store session info for feedback
            currentSession.sessionId = data.session_id;
            currentSession.query = query;
            
            const parsedResult = isHostname 
                ? parseHostnameResponse(markdown)
                : parseMarkdownResponse(markdown);
            
            // Store selected SRM and alternatives
            if (parsedResult.type === 'success') {
                currentSession.selectedSrm = {
                    name: parsedResult.name,
                    id: parsedResult.srmId || parsedResult.name // Use actual SRM_ID if available
                };
                currentSession.alternatives = parsedResult.alternatives || [];
            }
            
            isHostname ? renderHostnameResults(parsedResult) : renderResults(parsedResult);
        } catch (error) {
            console.error('Search error:', error);
            renderEmptyState(i18n[currentLocale].connectionError, i18n[currentLocale].connectionErrorBody, 'error-state');
        } finally {
            searchBtn.setAttribute('aria-busy', 'false');
            resultsContainer.setAttribute('aria-busy', 'false');
            searchBtn.disabled = false;
            searchBtn.textContent = originalButtonText;
            searchBtn.classList.remove('searching');
        }
    };
    
    const submitFeedback = async (feedbackType, correctSrm = null, feedbackText = '') => {
        try {
            const feedbackData = {
                session_id: currentSession.sessionId,
                query: currentSession.query,
                feedback_type: feedbackType,
                incorrect_srm_id: feedbackType === 'positive' ? null : currentSession.selectedSrm?.id,
                incorrect_srm_name: feedbackType === 'positive' ? null : currentSession.selectedSrm?.name,
                correct_srm_id: correctSrm?.id || null,
                correct_srm_name: correctSrm?.name || null,
                feedback_text: feedbackText
            };
            
            const response = await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(feedbackData)
            });
            
            if (!response.ok) {
                throw new Error(`Feedback API error: ${response.status}`);
            }
            
            const result = await response.json();
            
            // Show success message
            showFeedbackToast(result.message || 'Thank you for your feedback!');
            
            return true;
        } catch (error) {
            console.error('Feedback error:', error);
            showFeedbackToast('Failed to submit feedback. Please try again.', 'error');
            return false;
        }
    };
    
    const showFeedbackToast = (message, type = 'success') => {
        const toast = document.createElement('div');
        toast.className = `feedback-toast feedback-toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };
    
    const openFeedbackModal = () => {
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'feedback-modal';
        modal.id = 'feedback-modal';
        
        let alternativesHtml = '';
        if (currentSession.alternatives && currentSession.alternatives.length > 0) {
            alternativesHtml = currentSession.alternatives.map((alt, idx) => 
                `<option value="${idx}">${sanitize(alt.name)}</option>`
            ).join('');
        }
        
        modal.innerHTML = `
            <div class="feedback-modal-content">
                <div class="feedback-modal-header">
                    <h2>Help us improve</h2>
                    <button class="feedback-modal-close" aria-label="Close">&times;</button>
                </div>
                <div class="feedback-modal-body">
                    <p>We recommended: <strong>${sanitize(currentSession.selectedSrm?.name || 'Unknown')}</strong></p>
                    <p>What should we have recommended instead?</p>
                    
                    <label for="correct-srm-select">Select the correct SRM:</label>
                    <select id="correct-srm-select">
                        <option value="">-- Choose from alternatives --</option>
                        ${alternativesHtml}
                        <option value="other">Something else (specify below)</option>
                    </select>
                    
                    <label for="feedback-text">Additional details (optional):</label>
                    <textarea id="feedback-text" rows="3" placeholder="e.g., 'I needed X instead of Y because...'"></textarea>
                </div>
                <div class="feedback-modal-footer">
                    <button class="btn-cancel">Cancel</button>
                    <button class="btn-submit">Submit Feedback</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        setTimeout(() => modal.classList.add('show'), 10);
        
        // Event listeners
        modal.querySelector('.feedback-modal-close').addEventListener('click', closeFeedbackModal);
        modal.querySelector('.btn-cancel').addEventListener('click', closeFeedbackModal);
        modal.querySelector('.btn-submit').addEventListener('click', async () => {
            const selectElem = document.getElementById('correct-srm-select');
            const textElem = document.getElementById('feedback-text');
            const selectedIdx = selectElem.value;
            
            let correctSrm = null;
            if (selectedIdx && selectedIdx !== 'other') {
                const alt = currentSession.alternatives[parseInt(selectedIdx)];
                correctSrm = { id: alt.srmId || alt.name, name: alt.name };
            }
            
            const success = await submitFeedback('correction', correctSrm, textElem.value);
            if (success) {
                closeFeedbackModal();
            }
        });
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeFeedbackModal();
            }
        });
    };
    
    const closeFeedbackModal = () => {
        const modal = document.getElementById('feedback-modal');
        if (modal) {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 300);
        }
    };

    const adjustMainPadding = () => {
        const wrapperHeight = finderWrapper.offsetHeight;
        mainContent.style.paddingBottom = `${wrapperHeight + 16}px`; // 16px for extra space
    };

    // --- EVENT HANDLERS ---
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        runSearch(input.value);
    });

    suggestionContainer.addEventListener('click', (e) => {
        if (e.target.tagName === 'BUTTON') {
            const query = e.target.textContent;
            input.value = query;
            runSearch(query);
        }
    });
    
    // Event delegation for feedback buttons
    resultsContainer.addEventListener('click', async (e) => {
        const btn = e.target.closest('.feedback-btn');
        if (!btn) return;
        
        const action = btn.dataset.action;
        
        if (action === 'positive') {
            // Submit positive feedback immediately
            await submitFeedback('positive');
            btn.disabled = true;
            btn.innerHTML = '<span class="feedback-icon">✓</span> Thank you!';
        } else if (action === 'negative') {
            // Open modal for correction
            openFeedbackModal();
        }
    });
    
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            input.value = '';
        }
    });

    localeSwitcher.addEventListener('change', (e) => {
        currentLocale = e.target.value;
        updateUIStrings();
        // Note: Results are not re-rendered on locale change as they come from the backend in English
    });
    
    themeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            handleThemeChange(e.target.value);
        });
    });

    // --- SRM UPDATE CHAT ---
    
    const updateSrmBtn = document.getElementById('update-srm-btn');
    const srmUpdateModal = document.getElementById('srm-update-modal');
    const closeChatBtn = document.getElementById('close-chat-btn');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendChatBtn = document.getElementById('send-chat-btn');
    const chatStatus = document.getElementById('chat-status');
    
    let currentChatSessionId = null;
    let isWaitingForResponse = false;
    
    const openSrmUpdateChat = () => {
        srmUpdateModal.classList.add('show');
        srmUpdateModal.setAttribute('aria-hidden', 'false');
        chatInput.focus();
        
        // Reset chat for new session
        if (!currentChatSessionId) {
            chatMessages.innerHTML = `
                <div class="chat-message agent-message">
                    <div class="message-content">
                        <p><strong>Hi there! 👋</strong></p>
                        <p>I can help you update or modify SRM documents.</p>
                        <p><strong>Here's how it works:</strong></p>
                        <ol style="margin: 0.5rem 0 0.5rem 1.5rem; padding: 0;">
                            <li>Tell me which SRM you want to update</li>
                            <li>Describe what needs to change (owner notes or hidden notes)</li>
                            <li>Explain briefly why the change is needed</li>
                        </ol>
                        <p>Would you like to start by telling me which SRM you want to update?</p>
                    </div>
                </div>
            `;
            chatStatus.textContent = '';
            chatStatus.className = 'chat-status';
        }
    };
    
    const closeSrmUpdateChat = () => {
        srmUpdateModal.classList.remove('show');
        srmUpdateModal.setAttribute('aria-hidden', 'true');
        
        // Reset session if completed or escalated
        const statusClass = chatStatus.className;
        if (statusClass.includes('success') || statusClass.includes('warning')) {
            currentChatSessionId = null;
            chatInput.value = '';
        }
    };
    
    const formatAgentMessage = (content) => {
        // Basic markdown-style formatting for agent messages
        let formatted = sanitize(content);
        
        // Convert **bold** to <strong>
        formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        
        // Convert *italic* to <em>
        formatted = formatted.replace(/\*(.+?)\*/g, '<em>$1</em>');
        
        // Convert line breaks to paragraphs
        const paragraphs = formatted.split('\n\n').filter(p => p.trim());
        if (paragraphs.length > 1) {
            formatted = paragraphs.map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
        } else {
            formatted = `<p>${formatted.replace(/\n/g, '<br>')}</p>`;
        }
        
        return formatted;
    };
    
    const addMessageToChat = (content, isUser = false) => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${isUser ? 'user-message' : 'agent-message'}`;
        
        const formattedContent = isUser ? `<p>${sanitize(content)}</p>` : formatAgentMessage(content);
        
        messageDiv.innerHTML = `
            <div class="message-content">
                ${formattedContent}
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };
    
    const showTypingIndicator = () => {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'chat-message agent-message';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = `
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };
    
    const hideTypingIndicator = () => {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    };
    
    const updateChatStatus = (message, type = '') => {
        chatStatus.textContent = message;
        chatStatus.className = `chat-status ${type}`;
    };
    
    const sendChatMessage = async () => {
        const message = chatInput.value.trim();
        if (!message || isWaitingForResponse) return;
        
        // Add user message to chat
        addMessageToChat(message, true);
        chatInput.value = '';
        chatInput.style.height = 'auto';
        
        // Disable input while waiting
        isWaitingForResponse = true;
        sendChatBtn.disabled = true;
        chatInput.disabled = true;
        
        // Show typing indicator
        showTypingIndicator();
        
        try {
            const response = await fetch('/api/srm-update-chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: currentChatSessionId,
                    message: message
                })
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Update session ID
            currentChatSessionId = data.session_id;
            
            // Hide typing indicator
            hideTypingIndicator();
            
            // Add agent response
            addMessageToChat(data.response, false);
            
            // Update status based on response status
            if (data.status === 'completed') {
                updateChatStatus('✓ Update completed successfully!', 'success');
                setTimeout(() => {
                    closeSrmUpdateChat();
                }, 3000);
            } else if (data.status === 'escalated') {
                updateChatStatus('⚠ This request has been escalated to the support team.', 'warning');
            } else {
                updateChatStatus('');
            }
            
        } catch (error) {
            console.error('Chat error:', error);
            hideTypingIndicator();
            addMessageToChat('Sorry, I encountered an error. Please try again.', false);
            updateChatStatus('Error: Unable to process message', 'error');
        } finally {
            // Re-enable input
            isWaitingForResponse = false;
            sendChatBtn.disabled = false;
            chatInput.disabled = false;
            chatInput.focus();
        }
    };
    
    // Event Listeners for Chat
    updateSrmBtn.addEventListener('click', openSrmUpdateChat);
    closeChatBtn.addEventListener('click', closeSrmUpdateChat);
    
    // Close modal when clicking outside
    srmUpdateModal.addEventListener('click', (e) => {
        if (e.target === srmUpdateModal) {
            closeSrmUpdateChat();
        }
    });
    
    // Send message on button click
    sendChatBtn.addEventListener('click', sendChatMessage);
    
    // Send message on Enter key (Shift+Enter for new line)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });
    
    // Auto-resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    });

    // --- INITIALIZATION ---
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.getElementById(`theme-${savedTheme}`).checked = true;
        handleThemeChange(savedTheme);
    }
    updateUIStrings();
    
    adjustMainPadding();
    if ('ResizeObserver' in window) {
        new ResizeObserver(adjustMainPadding).observe(finderWrapper);
    }
});