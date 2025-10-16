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
        const categoryMatch = markdown.match(/\*\*Category:\*\*\s+(.+)/);
        const useCaseMatch = markdown.match(/\*\*Use Case:\*\*\s+(.+)/);
        const owningTeamMatch = markdown.match(/\*\*Owning Team:\*\*\s+(.+)/);
        const urlMatch = markdown.match(/\*\*URL:\*\*\s+(.+)/);
        
        if (!nameMatch) {
            // No matching SRM found
            return { type: 'no_results', message: markdown };
        }
        
        const result = {
            type: 'success',
            name: nameMatch[1].trim(),
            category: categoryMatch ? categoryMatch[1].trim() : '',
            useCase: useCaseMatch ? useCaseMatch[1].trim() : '',
            owningTeam: owningTeamMatch ? owningTeamMatch[1].trim() : '',
            url: urlMatch ? urlMatch[1].trim() : '',
            alternatives: []
        };
        
        // Parse alternatives section
        const alternativesSection = markdown.split('### Alternative Options:')[1];
        if (alternativesSection) {
            const altLines = alternativesSection.split('\n');
            let currentAlt = null;
            
            for (const line of altLines) {
                // Match numbered alternatives: "1. **Name** (Category) - Use case"
                const altMatch = line.match(/^\d+\.\s+\*\*(.+?)\*\*\s+\((.+?)\)\s+-\s+(.+)/);
                if (altMatch) {
                    if (currentAlt) {
                        result.alternatives.push(currentAlt);
                    }
                    currentAlt = {
                        name: altMatch[1].trim(),
                        category: altMatch[2].trim(),
                        useCase: altMatch[3].trim(),
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
        
        // Add alternatives section
        if (parsedResult.alternatives && parsedResult.alternatives.length > 0) {
            cardContent += `<div class="srm-alternatives">
                <h3>Alternative Options:</h3>
                <ol class="alternatives-list">`;
            
            parsedResult.alternatives.forEach(alt => {
                cardContent += `
                    <li class="alternative-item">
                        <strong>${sanitize(alt.name)}</strong> (${sanitize(alt.category)}) - ${sanitize(alt.useCase)}`;
                
                if (alt.url) {
                    cardContent += `<br><a href="${sanitize(alt.url)}" class="srm-url" target="_blank" rel="noopener noreferrer">${sanitize(alt.url)}</a>`;
                }
                
                cardContent += `</li>`;
            });
            
            cardContent += `</ol></div>`;
        }
        
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
            const markdown = isHostname 
                ? await realBackendHostnameSearch(processedQuery)
                : await realBackendSearch(query);
            
            const parsedResult = isHostname 
                ? parseHostnameResponse(markdown)
                : parseMarkdownResponse(markdown);
            
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