document.addEventListener('DOMContentLoaded', () => {
    // --- ИЗМЕНЕНИЕ: Обертка для ожидания готовности API PyWebView ---
    window.addEventListener('pywebviewready', () => {
        const minimizeBtn = document.getElementById('minimize-btn');
        const maximizeBtn = document.getElementById('maximize-btn');
        const closeBtn = document.getElementById('close-btn');

        if (minimizeBtn && window.pywebview && window.pywebview.api) {
            minimizeBtn.addEventListener('click', () => window.pywebview.api.minimize());
            maximizeBtn.addEventListener('click', () => window.pywebview.api.toggle_maximize());
            closeBtn.addEventListener('click', () => window.pywebview.api.close());
        }
    });
    // --- КОНЕЦ ИЗМЕНЕНИЯ ---

    // ИЗМЕНЕНИЕ: Глобальный слушатель для уведомлений о завершении загрузки
    window.addEventListener('download-finished', (e) => {
        const { status, message } = e.detail;
        if (status !== 'cancelled') {
            // Показываем alert, так как мы не на странице настроек
            alert(`Загрузка завершена!\nСтатус: ${status}\nСообщение: ${message}`);
        }
    });


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

    function applyTheme(theme) {
        if (theme === 'system') {
            const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', systemTheme);
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
        localStorage.setItem('theme', theme);
    }

    if (themeSelect) {
        themeSelect.addEventListener('change', (e) => {
            applyTheme(e.target.value);
        });

        const savedTheme = localStorage.getItem('theme') || 'system';
        themeSelect.value = savedTheme;
        applyTheme(savedTheme);
    } else {
        // Apply theme on pages without a selector
        const savedTheme = localStorage.getItem('theme') || 'system';
        applyTheme(savedTheme);
    }

    let chats = {};
    let activeChatId = null;

    function saveChats() {
        localStorage.setItem('chats', JSON.stringify(chats));
    }

    function loadChats() {
        const savedChats = localStorage.getItem('chats');
        if (savedChats) {
            chats = JSON.parse(savedChats);
        }
    }

    const sidebar = document.querySelector('.sidebar');

    sidebar.addEventListener('mouseenter', () => {
        sidebar.classList.remove('collapsed');
    });

    sidebar.addEventListener('mouseleave', () => {
        sidebar.classList.add('collapsed');
    });
    let chatsVisible = false;

    function renderChatList() {
        chatList.innerHTML = '';
        const chatIds = Object.keys(chats);

        const visibleChats = chatsVisible ? chatIds : chatIds.slice(0, 8);

        for (const id of visibleChats) {
            const chat = chats[id];
            const chatDiv = document.createElement('div');
            chatDiv.classList.add('chat-item');
            if (id === activeChatId) {
                chatDiv.classList.add('active');
            }

            const chatTitle = document.createElement('span');
            chatTitle.classList.add('chat-title');
            chatTitle.textContent = chat.title.length > 30 ? chat.title.substring(0, 27) + '...' : chat.title;
            chatDiv.appendChild(chatTitle);

            const editBtn = document.createElement('button');
            editBtn.innerHTML = '✎'; // Edit icon
            editBtn.classList.add('edit-btn');
            editBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const newTitle = prompt('Enter new chat title:', chat.title);
                if (newTitle) {
                    chats[id].title = newTitle;
                    saveChats();
                    renderChatList();
                }
            });

            const deleteBtn = document.createElement('button');
            deleteBtn.innerHTML = ''; // Trash icon
            deleteBtn.classList.add('delete-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (confirm('Are you sure you want to delete this chat?')) {
                    delete chats[id];
                    if (activeChatId === id) {
                        activeChatId = Object.keys(chats)[0] || null;
                        if(activeChatId) {
                            switchChat(activeChatId);
                        } else {
                            createNewChat();
                        }
                    }
                    saveChats();
                    renderChatList();
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
        activeChatId = chatId;
        const chat = chats[chatId];
        settingInput.value = chat.setting;
        resultBox.textContent = chat.result;
        renderChatList();
    }

    function createNewChat() {
        const newChatId = `chat_${Date.now()}`;
        chats[newChatId] = {
            id: newChatId,
            title: `Чат ${Object.keys(chats).length + 1}`,
            setting: '',
            result: 'Здесь появится сгенерированный JSON...'
        };
        activeChatId = newChatId;
        saveChats();
        renderChatList();
        switchChat(newChatId);
    }

    newChatBtn.addEventListener('click', createNewChat);

    settingsBtn.addEventListener('click', () => {
        window.location.href = '/settings';
    });

    async function updateModels() {
        const selectedProvider = document.querySelector('input[name="api_provider"]:checked').value;

        if (selectedProvider === 'local') {
            try {
                const response = await fetch('/api/local_models');
                const data = await response.json();
                if (response.ok && data.models) {
                    modelSelector.innerHTML = '';
                    // ИЗМЕНЕНИЕ: Обработка нового формата ответа (список объектов)
                    data.models.forEach(model => {
                        const option = document.createElement('option');
                        option.value = model.name;
                        option.textContent = model.name;
                        modelSelector.appendChild(option);
                    });
                    modelSelectorGroup.style.display = 'block';
                } else {
                    modelSelectorGroup.style.display = 'none';
                    console.error('Failed to fetch local models:', data.error);
                }
            } catch (error) {
                modelSelectorGroup.style.display = 'none';
                console.error('Error fetching local models:', error);
            }
            return;
        }

        const apiKey = localStorage.getItem(`${selectedProvider}_api_key`);
        const cachedModels = localStorage.getItem(`${selectedProvider}_models`);

        if (!apiKey && selectedProvider !== 'local') {
            modelSelectorGroup.style.display = 'none';
            return;
        }

        if (cachedModels) {
            const models = JSON.parse(cachedModels);
            modelSelector.innerHTML = '';
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                modelSelector.appendChild(option);
            });
            modelSelectorGroup.style.display = 'block';
            return;
        }

        try {
            const response = await fetch('/api/models', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    api_provider: selectedProvider,
                    api_key: apiKey,
                }),
            });

            const data = await response.json();

            if (response.ok && data.models) {
                localStorage.setItem(`${selectedProvider}_models`, JSON.stringify(data.models));
                modelSelector.innerHTML = '';
                data.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    modelSelector.appendChild(option);
                });
                modelSelectorGroup.style.display = 'block';
            } else {
                modelSelectorGroup.style.display = 'none';
                console.error('Failed to fetch models:', data.error);
            }
        } catch (error) {
            modelSelectorGroup.style.display = 'none';
            console.error('Error fetching models:', error);
        }
    }

    providerRadios.forEach(radio => {
        radio.addEventListener('change', updateModels);
    });

    const resultBoxWrapper = document.getElementById('result-box-wrapper');

    const upArrow = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z"/></svg>`;
    const downArrow = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/></svg>`;

    function toggleResultView(isVisible) {
        resultBoxWrapper.style.display = isVisible ? 'block' : 'none';
        toggleResultBtn.innerHTML = isVisible ? upArrow : downArrow;
    }

    toggleResultBtn.addEventListener('click', () => {
        const isVisible = resultBoxWrapper.style.display !== 'none';
        toggleResultView(!isVisible);
    });

    // Initial state
    toggleResultView(true);

    downloadResultBtn.addEventListener('click', async () => {
        const resultJson = resultBox.textContent;
        try {
            // Проверяем, что в блоке валидный JSON
            JSON.parse(resultJson);
    
            if (window.pywebview && window.pywebview.api) {
                // Вызываем нативный диалог сохранения через Python
                await window.pywebview.api.save_quest_to_file(resultJson);
            } else {
                // Если API не доступно (например, при отладке в обычном браузере),
                // выводим сообщение об ошибке, так как это ключевая функция десктопного приложения.
                alert("Функция сохранения доступна только в десктопном приложении.");
                console.error("PyWebView API not found. Cannot trigger download.");
            }
        } catch (e) {
            // Это сработает, если в resultBox невалидный JSON (например, текст ошибки или "Генерация...")
            alert('Невозможно скачать, так как результат не является валидным JSON.');
        }
    });

    generateBtn.addEventListener('click', async () => {
        if (!activeChatId) {
            createNewChat();
        }

        const setting = settingInput.value.trim();
        const selectedProvider = document.querySelector('input[name="api_provider"]:checked').value;
        const selectedModel = modelSelector.value;
        const apiKey = localStorage.getItem(`${selectedProvider}_api_key`);

        if (!setting) {
            alert('Пожалуйста, введите сеттинг.');
            return;
        }

        if (!apiKey && selectedProvider !== 'local') {
            alert(`API-ключ для провайдера "${selectedProvider}" не найден. Пожалуйста, добавьте его на странице настройки ключей.`);
            window.location.href = '/api_keys';
            return;
        }

        if (!selectedModel) {
            alert('Пожалуйста, выберите модель.');
            return;
        }

        resultBox.textContent = 'Генерация... Пожалуйста, подождите.';
        generateBtn.disabled = true;

        chats[activeChatId].setting = setting;

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    setting: setting,
                    api_key: apiKey,
                    api_provider: selectedProvider,
                    model: selectedModel,
                }),
            });

            const data = await response.json();

            if (response.ok) {
                const result = JSON.stringify(data, null, 2);
                resultBox.textContent = result;
                chats[activeChatId].result = result;
            } else {
                const error = `Ошибка: ${data.error || 'Неизвестная ошибка сервера'}`;
                resultBox.textContent = error;
                chats[activeChatId].result = error;
            }
        } catch (error) {
            console.error('Fetch Error:', error);
            const errorMsg = 'Сетевая ошибка или не удалось обработать запрос. Проверьте консоль (F12).';
            resultBox.textContent = errorMsg;
            chats[activeChatId].result = errorMsg;
        } finally {
            generateBtn.disabled = false;
            saveChats();
        }
    });

    loadChats();
    if (Object.keys(chats).length === 0) {
        createNewChat();
    } else {
        activeChatId = Object.keys(chats)[0];
        switchChat(activeChatId);
    }
    renderChatList();
    updateModels();
});