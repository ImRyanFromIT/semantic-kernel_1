document.addEventListener('DOMContentLoaded', () => {

    // --- DATA ---
    const i18n = {
        en: {
            problemLabel: "Describe your problem",
            helperText: "Be as specific as possible.",
            search: "Search",
            searching: "Searching...",
            searchingMessage: "Searching for the right SRM...",
            suggestions: [
                "Expand storage on a file share",
                "Restore deleted files",
                "Add more CPU to a VM"
            ],
            resultFound: "1 result found.",
            firstResult: "The result is",
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
            problemLabel: "Describa su problema",
            helperText: "Sea lo más específico posible.",
            search: "Buscar",
            searching: "Buscando...",
            searchingMessage: "Buscando el SRM correcto...",
            suggestions: [
                "Ampliar almacenamiento",
                "Restaurar archivos",
                "Añadir más CPU a una VM"
            ],
            resultFound: "1 resultado encontrado.",
            firstResult: "El resultado es",
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
    
    const realBackendSearch = async (query) => {
        try {
            const response = await fetch('/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            return data.response; // Returns markdown string
        } catch (error) {
            console.error('Backend search error:', error);
            throw error;
        }
    };
    
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

        const announcement = `${i18n[currentLocale].firstResult} ${parsedResult.name}.`;
        srAnnouncer.textContent = announcement;
        setTimeout(() => srAnnouncer.textContent = '', 1000);
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

    const runSearch = async (query) => {
        if (!query.trim()) return;

        // Store original button text
        const originalButtonText = searchBtn.textContent;
        
        // Set loading state
        searchBtn.setAttribute('aria-busy', 'true');
        resultsContainer.setAttribute('aria-busy', 'true');
        searchBtn.disabled = true;
        searchBtn.textContent = i18n[currentLocale].searching;
        searchBtn.classList.add('searching');
        
        // Show loading indicator in results
        resultsContainer.innerHTML = `
            <div class="loading-state" data-testid="loading-state">
                <div class="spinner"></div>
                <p>${i18n[currentLocale].searchingMessage}</p>
            </div>
        `;
        
        try {
            const markdown = await realBackendSearch(query);
            const parsedResult = parseMarkdownResponse(markdown);
            renderResults(parsedResult);
        } catch (error) {
            console.error('Search error:', error);
            resultsContainer.innerHTML = `
                <div class="empty-state" data-testid="error-state">
                    <h3>${i18n[currentLocale].connectionError}</h3>
                    <p>${i18n[currentLocale].connectionErrorBody}</p>
                </div>
            `;
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