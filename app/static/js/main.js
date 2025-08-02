// Вся логика теперь будет выполняться только после того, как pywebview API будет полностью готово.
window.addEventListener('pywebviewready', async () => {
    // ==================== API И КОНСТАНТЫ ====================
    const api = window.pywebview.api;
    const minimizeBtn = document.getElementById('minimize-btn');
    const maximizeBtn = document.getElementById('maximize-btn');
    const closeBtn = document.getElementById('close-btn');
    const generateBtn = document.getElementById('generate-btn');
    const settingInput = document.getElementById('setting-input');
    const resultBox = document.getElementById('result-box');
    const providerRadios = document.querySelectorAll('input[name="api_provider"]');
    const modelSelectorGroup = document.getElementById('model-selector-group');
    const modelSelector = document.getElementById('model-selector');
    const newChatBtn = document.getElementById('new-chat-btn');
    const chatList = document.getElementById('chat-list');
    const settingsBtn = document.getElementById('settings-btn');
    const toggleResultBtn = document.getElementById('toggle-result-btn');
    const downloadResultBtn = document.getElementById('download-result-btn');
    const themeSelect = document.getElementById('theme-select');
    const resultBoxWrapper = document.getElementById('result-box-wrapper');
    const sidebar = document.querySelector('.sidebar');

    window.chats = {};
    window.activeChatId = null;
    let saveTimeout = null;
    let chatsVisible = false;

    // ==================== КЛЮЧЕВЫЕ ФУНКЦИИ (ЗАГРУЗКА/СОХРАНЕНИЕ) ====================

    async function saveChats() {
        try {
            const stateToSave = {
                chats: window.chats,
                activeChatId: window.activeChatId,
            };
            await api.save_chats_to_disk(stateToSave);
        } catch (e) {
            console.error("Failed to save chats via Python API:", e);
        }
    }
    window.saveChats = saveChats;

    async function loadChats() {
        try {
            const persistedState = await api.load_chats_from_disk();
            if (persistedState && persistedState.chats) {
                window.chats = persistedState.chats;
                window.activeChatId = persistedState.activeChatId;
            } else {
                window.chats = {};
                window.activeChatId = null;
            }
        } catch (e) {
            console.error("Failed to load chats from Python API:", e);
            window.chats = {};
            window.activeChatId = null;
        }
    }

    async function syncApiKeysFromFileToLocalStorage() {
        try {
            const savedKeys = await api.load_api_keys();
            if (savedKeys) {
                localStorage.setItem('groq_api_key', savedKeys.groq || '');
                localStorage.setItem('openai_api_key', savedKeys.openai || '');
                localStorage.setItem('gemini_api_key', savedKeys.gemini || '');
                console.log('API keys synced from file to localStorage.');
            }
        } catch (e) {
            console.error("Could not sync API keys from file:", e);
        }
    }

    // ==================== ОСТАЛЬНАЯ ЛОГИКА ПРИЛОЖЕНИЯ ====================

    function debouncedSaveChats() {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(saveChats, 500);
    }

    function applyTheme(theme) {
        if (theme === 'system') {
            const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', systemTheme);
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
        localStorage.setItem('theme', theme);
    }

    function renderChatList() {
        chatList.innerHTML = '';
        const chatIds = Object.keys(window.chats);
        const visibleChats = chatsVisible ? chatIds : chatIds.slice(0, 8);

        for (const id of visibleChats) {
            const chat = window.chats[id];
            const chatDiv = document.createElement('div');
            chatDiv.classList.add('chat-item');
            if (id === window.activeChatId) {
                chatDiv.classList.add('active');
            }

            const chatTitle = document.createElement('span');
            chatTitle.classList.add('chat-title');
            chatTitle.textContent = chat.title.length > 30 ? chat.title.substring(0, 27) + '...' : chat.title;
            chatDiv.appendChild(chatTitle);

            const editBtn = document.createElement('button');
            editBtn.innerHTML = '✎';
            editBtn.classList.add('edit-btn');
            editBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const newTitle = prompt('Введите новое название чата:', chat.title);
                if (newTitle && newTitle.trim()) {
                    window.chats[id].title = newTitle.trim();
                    saveChats();
                    renderChatList();
                }
            });

            const deleteBtn = document.createElement('button');
            // ==================== ИЗМЕНЕНИЕ: Иконка заменена на SVG ====================
            // Эта SVG-иконка будет автоматически окрашена в красный цвет благодаря CSS-классу '.delete-btn'
            const deleteIconSVG = `<svg xmlns="http://www.w3.org/2000/svg" height="18px" viewBox="0 0 24 24" width="18px" fill="currentColor"><path d="M0 0h24v24H0V0z" fill="none"/><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>`;
            deleteBtn.innerHTML = deleteIconSVG;
            // =========================================================================
            deleteBtn.classList.add('delete-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (confirm(`Вы уверены, что хотите удалить "${chat.title}"?`)) {
                    const idToDelete = id;
                    delete window.chats[idToDelete];
                    if (window.activeChatId === idToDelete) {
                        window.activeChatId = Object.keys(window.chats)[0] || null;
                        if (window.activeChatId) {
                            switchChat(window.activeChatId);
                        } else {
                            createNewChat();
                        }
                    } else {
                        saveChats();
                        renderChatList();
                    }
                }
            });

            const chatActions = document.createElement('div');
            chatActions.classList.add('chat-actions');
            chatActions.appendChild(editBtn);
            chatActions.appendChild(deleteBtn);
            chatDiv.appendChild(chatActions);

            chatDiv.dataset.chatId = id;
            chatDiv.addEventListener('click', () => {
                switchChat(id);
            });
            chatList.appendChild(chatDiv);
        }

        if (chatIds.length > 8) {
            const toggleBtn = document.createElement('button');
            toggleBtn.textContent = chatsVisible ? 'Свернуть' : 'Развернуть';
            toggleBtn.addEventListener('click', () => {
                chatsVisible = !chatsVisible;
                renderChatList();
            });
            chatList.appendChild(toggleBtn);
        }
    }

    function switchChat(chatId) {
        window.activeChatId = chatId;
        const chat = window.chats[chatId];
        settingInput.value = chat.setting;
        resultBox.textContent = chat.result;
        renderChatList();
        saveChats();
    }

    function createNewChat() {
        const newChatId = `chat_${Date.now()}`;
        window.chats[newChatId] = {
            id: newChatId,
            title: `Новый чат ${Object.keys(window.chats).length + 1}`,
            setting: '',
            result: 'Здесь появится сгенерированный JSON...'
        };
        renderChatList();
        switchChat(newChatId);
    }

    async function updateModels() {
        const selectedProvider = document.querySelector('input[name="api_provider"]:checked').value;
        modelSelector.innerHTML = '';
        modelSelectorGroup.style.display = 'none';

        if (selectedProvider === 'local') {
            try {
                const response = await fetch('/api/local_models');
                const data = await response.json();
                if (response.ok && data.models && data.models.length > 0) {
                    data.models.forEach(model => {
                        const option = document.createElement('option');
                        option.value = model.name;
                        option.textContent = model.name;
                        modelSelector.appendChild(option);
                    });
                    modelSelectorGroup.style.display = 'block';
                }
            } catch (error) { console.error('Error fetching local models:', error); }
            return;
        }

        const apiKey = localStorage.getItem(`${selectedProvider}_api_key`);
        if (!apiKey) return;

        const createOptgroup = (label, models) => {
            if (models && models.length > 0) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = label;
                models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    optgroup.appendChild(option);
                });
                modelSelector.appendChild(optgroup);
            }
        };

        const cachedModelsRaw = localStorage.getItem(`${selectedProvider}_models`);
        if (cachedModelsRaw) {
            try {
                const data = JSON.parse(cachedModelsRaw);
                if (data && (data.free || data.paid)) {
                    createOptgroup('Бесплатные / Стандартные', data.free);
                    createOptgroup('Платные / Продвинутые', data.paid);
                    modelSelectorGroup.style.display = 'block';
                    return;
                }
            } catch (e) { localStorage.removeItem(`${selectedProvider}_models`); }
        }

        try {
            const response = await fetch('/api/models', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_provider: selectedProvider, api_key: apiKey }),
            });
            const data = await response.json();
            if (response.ok && (data.free || data.paid)) {
                localStorage.setItem(`${selectedProvider}_models`, JSON.stringify(data));
                createOptgroup('Бесплатные / Стандартные', data.free);
                createOptgroup('Платные / Продвинутые', data.paid);
                if ((data.free && data.free.length > 0) || (data.paid && data.paid.length > 0)) {
                    modelSelectorGroup.style.display = 'block';
                }
            }
        } catch (error) { console.error('Error fetching models:', error); }
    }

    function toggleResultView(isVisible) {
        const upArrow = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/></svg>`;
        const downArrow = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/></svg>`;
        resultBoxWrapper.style.display = isVisible ? 'block' : 'none';
        toggleResultBtn.innerHTML = isVisible ? upArrow : downArrow;
    }

    // ==================== ЗАПУСК ИНИЦИАЛИЗАЦИИ И ПРИВЯЗКА СОБЫТИЙ ====================

    if (minimizeBtn) minimizeBtn.addEventListener('click', () => api.minimize());
    if (maximizeBtn) maximizeBtn.addEventListener('click', () => api.toggle_maximize());
    if (closeBtn) closeBtn.addEventListener('click', () => api.close());
    
    if (sidebar) {
        sidebar.addEventListener('mouseenter', () => sidebar.classList.remove('collapsed'));
        sidebar.addEventListener('mouseleave', () => sidebar.classList.add('collapsed'));
    }

    newChatBtn.addEventListener('click', createNewChat);
    settingsBtn.addEventListener('click', () => { window.location.href = '/settings'; });

    settingInput.addEventListener('input', () => {
        if (window.activeChatId && window.chats[window.activeChatId]) {
            window.chats[window.activeChatId].setting = settingInput.value;
            debouncedSaveChats();
        }
    });

    settingInput.addEventListener('blur', () => {
        clearTimeout(saveTimeout);
        saveChats();
    });

    providerRadios.forEach(radio => radio.addEventListener('change', updateModels));

    toggleResultBtn.addEventListener('click', () => {
        const isVisible = resultBoxWrapper.style.display !== 'none';
        toggleResultView(!isVisible);
    });

    downloadResultBtn.addEventListener('click', async () => {
        try {
            JSON.parse(resultBox.textContent);
            await api.save_quest_to_file(resultBox.textContent);
        } catch (e) {
            alert('Невозможно скачать, так как результат не является валидным JSON.');
        }
    });

    generateBtn.addEventListener('click', async () => {
        if (!window.activeChatId) createNewChat();
        
        const setting = settingInput.value.trim();
        const selectedProvider = document.querySelector('input[name="api_provider"]:checked').value;
        const selectedModel = modelSelector.value;
        const apiKey = localStorage.getItem(`${selectedProvider}_api_key`) || '';

        if (!setting || !selectedModel || (!apiKey && selectedProvider !== 'local')) {
            alert('Пожалуйста, введите сеттинг, выберите модель и убедитесь, что API ключ добавлен.');
            return;
        }

        resultBox.textContent = 'Генерация... Пожалуйста, подождите.';
        generateBtn.disabled = true;
        window.chats[window.activeChatId].setting = setting;

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    setting: setting,
                    api_key: apiKey,
                    api_provider: selectedProvider,
                    model: selectedModel,
                }),
            });
            const data = await response.json();
            const resultText = response.ok ? JSON.stringify(data, null, 2) : `Ошибка: ${data.error || 'Неизвестная ошибка сервера'}`;
            resultBox.textContent = resultText;
            window.chats[window.activeChatId].result = resultText;
        } catch (error) {
            console.error('Fetch Error:', error);
            const errorMsg = 'Сетевая ошибка или не удалось обработать запрос.';
            resultBox.textContent = errorMsg;
            window.chats[window.activeChatId].result = errorMsg;
        } finally {
            generateBtn.disabled = false;
            saveChats();
        }
    });

    if (themeSelect) {
        const savedTheme = localStorage.getItem('theme') || 'system';
        themeSelect.value = savedTheme;
        applyTheme(savedTheme);
        themeSelect.addEventListener('change', (e) => applyTheme(e.target.value));
    } else {
        applyTheme(localStorage.getItem('theme') || 'system');
    }
    
    // ==================== ГЛАВНЫЙ ЗАПУСК ====================
    await syncApiKeysFromFileToLocalStorage();
    await loadChats();
    
    if (window.activeChatId && window.chats[window.activeChatId]) {
        switchChat(window.activeChatId);
    } else if (Object.keys(window.chats).length > 0) {
        const firstChatId = Object.keys(window.chats)[0];
        switchChat(firstChatId);
    } else {
        createNewChat();
    }
    
    renderChatList();
    updateModels();
    toggleResultView(true);
});

window.addEventListener('download-finished', (e) => {
    const { status, message } = e.detail;
    if (status !== 'cancelled') {
        alert(`Загрузка завершена!\nСтатус: ${status}\nСообщение: ${message}`);
    }
});