document.addEventListener('DOMContentLoaded', () => {

    // --- DATA ---
    const srmData = [
        { id: 1, name: "Connector: Storage Expansion", description: "Request additional storage capacity for an existing network file share or drive." },
        { id: 2, name: "Connector: File Restoration", description: "Request the restoration of files or folders from a backup for a server or file share." },
        { id: 3, name: "Connector: VM Resource Adjustment", description: "Increase the CPU core count or memory (RAM) allocated to an existing virtual machine." },
        { id: 4, name: "Connector: New Virtual Machine", description: "Provision a new virtual machine with a standard operating system build." },
    ];

    const i18n = {
        en: {
            problemLabel: "Describe your problem",
            helperText: "Be as specific as possible.",
            search: "Search",
            suggestions: [
                "Expand storage on a file share",
                "Restore deleted files",
                "Add more CPU to a VM"
            ],
            resultFound: "1 result found.",
            firstResult: "The result is",
            noResultsTitle: "No matching Connector found",
            noResultsBody: "Your request will be routed to a general queue. Please submit it and a team member will assist you.",
            language: "Language:",
            themeSystem: "System",
            themeLight: "Light",
            themeDark: "Dark"
        },
        es: {
            problemLabel: "Describa su problema",
            helperText: "Sea lo más específico posible.",
            search: "Buscar",
            suggestions: [
                "Ampliar almacenamiento",
                "Restaurar archivos",
                "Añadir más CPU a una VM"
            ],
            resultFound: "1 resultado encontrado.",
            firstResult: "El resultado es",
            noResultsTitle: "No se encontró ningún Conector coincidente",
            noResultsBody: "Su solicitud se enviará a una cola general. Envíela y un miembro del equipo le ayudará.",
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
    
    const mockBackendSearch = (query) => {
        const normalizedQuery = query.toLowerCase().trim();
        if (normalizedQuery.includes('storage')) return [srmData[0]];
        if (normalizedQuery.includes('restore') || normalizedQuery.includes('restaurar')) return [srmData[1]];
        if (normalizedQuery.includes('cpu')) return [srmData[2]];
        if (normalizedQuery) return [srmData[3]];
        return [];
    };

    const renderResults = (results) => {
        resultsContainer.innerHTML = '';
        
        if (results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="empty-state" data-testid="empty-state">
                    <h3>${i18n[currentLocale].noResultsTitle}</h3>
                    <p>${i18n[currentLocale].noResultsBody}</p>
                </div>
            `;
            return;
        }

        const result = results[0];

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
        listItem.setAttribute('data-testid', `srm-card-${result.id}`);
        
        listItem.innerHTML = `<h2 data-testid="srm-name">${sanitize(result.name)}</h2>`;

        list.appendChild(listItem);
        resultsContainer.appendChild(list);

        const announcement = `${i18n[currentLocale].firstResult} ${result.name}.`;
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

    const runSearch = (query) => {
        if (!query.trim()) return;

        searchBtn.setAttribute('aria-busy', 'true');
        resultsContainer.setAttribute('aria-busy', 'true');
        
        setTimeout(() => {
            const results = mockBackendSearch(query);
            renderResults(results);
            searchBtn.setAttribute('aria-busy', 'false');
            resultsContainer.setAttribute('aria-busy', 'false');
        }, 250);
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
        if (resultsContainer.innerHTML.trim() !== '') {
            const query = input.value;
            if (query.trim()) {
                const results = mockBackendSearch(query);
                renderResults(results);
            }
        }
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