// Вся логика теперь будет выполняться только после того, как pywebview API будет полностью готово.
window.addEventListener('pywebviewready', async () => {
    // ==================== API И КОНСТАНТЫ ====================
    const api = window.pywebview.api;
    const tooltip = document.getElementById('graph-tooltip');
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
    const downloadResultBtn = document.getElementById('download-result-btn');
    const themeSelect = document.getElementById('theme-select');
    const resultBoxWrapper = document.getElementById('result-box-wrapper');
    const graphBox = document.getElementById('graph-box');
    const jsonTab = document.getElementById('json-tab');
    const graphTab = document.getElementById('graph-tab');
    const sidebar = document.querySelector('.sidebar');
    const editGraphBtn = document.getElementById('edit-graph-btn');
    const graphEditorPanel = document.getElementById('graph-editor-panel');
    const addSceneBtn = document.getElementById('add-scene-btn');


    window.chats = {};
    window.activeChatId = null;
    let saveTimeout = null;
    let chatsVisible = false;
    let editMode = false;

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

    // ==================== ЛОГИКА ГРАФА И РЕНДЕРИНГА ====================
    
    async function renderQuestGraph(jsonString) {
        graphBox.innerHTML = 'Подготовка графа...';

        await new Promise(resolve => setTimeout(resolve, 10));

        try {
            let questData;
            try {
                const intermediateParse = JSON.parse(jsonString);
                questData = (typeof intermediateParse === 'string') ? JSON.parse(intermediateParse) : intermediateParse;
            } catch (e) {
                throw new Error("Invalid JSON format");
            }

            if (!questData || !questData.scenes) {
                throw new Error("Неверная структура JSON для графа.");
            }
            if (!questData.start_scene && questData.scenes.length > 0) {
                questData.start_scene = questData.scenes[0].scene_id;
            }
            if (!questData.start_scene) {
                 throw new Error("В квесте нет начальной сцены.");
            }

            const sceneDataMap = new Map(questData.scenes.map(scene => [scene.scene_id, scene]));
            const allSceneIds = new Set(questData.scenes.map(s => s.scene_id));
            questData.scenes.forEach(scene => {
                scene.choices?.forEach(choice => {
                    if (choice && choice.next_scene) allSceneIds.add(choice.next_scene)
                });
            });

            const isDarkTheme = document.documentElement.getAttribute('data-theme') === 'dark';
            const themeVariables = {
                fontSize: '22px',
                primaryColor: isDarkTheme ? '#28252b' : '#ffffff',
                primaryTextColor: isDarkTheme ? '#ffffff' : '#000000',
                primaryBorderColor: isDarkTheme ? '#bfb8dd' : '#555555',
                lineColor: isDarkTheme ? '#bfb8dd' : '#555555',
                secondaryColor: '#715cd7',
                secondaryTextColor: '#ffffff',
                strokeWidth: '2px',
            };

            const formatEdgeLabel = (text, lineLength = 25) => {
                if (!text) return ' ';
                const escapedText = text.replace(/"/g, '#quot;');
                const words = escapedText.split(' ');
                const lines = [];
                let currentLine = "";
                for (const word of words) {
                    if (currentLine === "") currentLine = word;
                    else if (currentLine.length + 1 + word.length <= lineLength) currentLine += " " + word;
                    else { lines.push(currentLine); currentLine = word; }
                }
                if (currentLine) lines.push(currentLine);
                return lines.join('<br>');
            };

            let mermaidDefinition = `%%{init: {'theme': 'base', 'themeVariables': ${JSON.stringify(themeVariables)}}}%%\n`;
            mermaidDefinition += 'graph TD\n';

            allSceneIds.forEach(id => mermaidDefinition += `    ${id}["${id}"]\n`);

            sceneDataMap.forEach(scene => {
                scene.choices?.forEach(choice => {
                    if (choice && choice.next_scene) {
                        const formattedLabel = formatEdgeLabel(choice.text);
                        mermaidDefinition += `    ${scene.scene_id} -->|"${formattedLabel}"| ${choice.next_scene}\n`;
                    }
                });
            });

            mermaidDefinition += `    style ${questData.start_scene} fill:${themeVariables.secondaryColor},stroke:${themeVariables.secondaryColor},color:${themeVariables.secondaryTextColor},font-weight:bold\n`;

            graphBox.innerHTML = mermaidDefinition;
            graphBox.removeAttribute('data-processed');

            await mermaid.run({ nodes: [graphBox] });

            // Привязка подсказок и событий редактирования
            const svgNodes = graphBox.querySelectorAll('.node');
            svgNodes.forEach(svgNode => {
                const sceneId = svgNode.id.replace(/flowchart-(.*)-\d+/, '$1');

                // Standard mouse events for tooltip
                svgNode.addEventListener('mousemove', (e) => {
                    if (editMode) return;
                    tooltip.style.left = `${e.clientX + 15}px`;
                    tooltip.style.top = `${e.clientY + 15}px`;
                });
                svgNode.addEventListener('mouseover', () => {
                    if (editMode) return;
                    const sceneData = sceneDataMap.get(sceneId);
                    tooltip.innerHTML = sceneData
                        ? `<strong>${sceneData.scene_id}</strong><hr style="margin: 5px 0; border-color: ${themeVariables.primaryBorderColor};"><p>${sceneData.text}</p>`
                        : `<strong>${sceneId}</strong><hr style="margin: 5px 0; border-color: ${themeVariables.primaryBorderColor};"><p>Конец ветки.</p>`;
                    tooltip.style.display = 'block';
                });
                svgNode.addEventListener('mouseout', () => {
                    tooltip.style.display = 'none';
                });

                // Add editing capabilities if in edit mode
                if (editMode) {
                    svgNode.classList.add('editable');
                    svgNode.addEventListener('click', () => openEditModal(sceneId));
                }
            });

        } catch (error) {
            console.error("Ошибка рендеринга графа:", error);
            graphBox.innerHTML = `<p class="status-error">Не удалось построить граф. Проверьте валидность и структуру JSON.</p>`;
        }
    }


    // ==================== ЛОГИКА РЕДАКТОРА ГРАФА ====================

    function getCurrentQuestData() {
        if (!window.activeChatId || !window.chats[window.activeChatId]) return null;
        try {
            const result = window.chats[activeChatId].result;
            if (!result || result.includes('Здесь появится')) return null;
            const data = JSON.parse(result);
            if (!Array.isArray(data.scenes)) data.scenes = [];
            return data;
        } catch (e) {
            console.error("Could not parse quest data:", e);
            return null;
        }
    }

    function saveQuestData(questData) {
        if (!window.activeChatId || !window.chats[activeChatId]) return;
        window.chats[activeChatId].result = JSON.stringify(questData, null, 2);
        saveChats();
        renderQuestGraph(window.chats[activeChatId].result);
    }

    function openEditModal(sceneId) {
        const questData = getCurrentQuestData();
        if (!questData) return;

        const scene = questData.scenes.find(s => s.scene_id === sceneId);
        if (!scene) {
            alert(`Ошибка: Сцена с ID "${sceneId}" не найдена.`);
            return;
        }

        const overlay = document.getElementById('edit-modal-overlay');
        const closeBtn = document.getElementById('modal-close-btn');
        const sceneIdInput = document.getElementById('modal-scene-id');
        const originalSceneIdInput = document.getElementById('modal-scene-id-original');
        const sceneTextInput = document.getElementById('modal-scene-text');
        const addChoiceBtn = document.getElementById('modal-add-choice-btn');
        const saveBtn = document.getElementById('modal-save-btn');
        const cancelBtn = document.getElementById('modal-cancel-btn');
        const deleteBtn = document.getElementById('modal-delete-scene-btn');
        const sceneIdError = document.getElementById('scene-id-error');

        originalSceneIdInput.value = scene.scene_id;
        sceneIdInput.value = scene.scene_id;
        sceneTextInput.value = scene.text || '';
        sceneIdError.style.display = 'none';
        sceneIdError.textContent = '';

        const allSceneIds = questData.scenes.map(s => s.scene_id);
        renderModalChoices(scene.choices || [], allSceneIds);

        const newSaveBtn = saveBtn.cloneNode(true);
        saveBtn.parentNode.replaceChild(newSaveBtn, saveBtn);
        newSaveBtn.addEventListener('click', saveSceneFromModal);

        const newDeleteBtn = deleteBtn.cloneNode(true);
        deleteBtn.parentNode.replaceChild(newDeleteBtn, deleteBtn);
        newDeleteBtn.addEventListener('click', () => deleteScene(scene.scene_id));

        const newAddChoiceBtn = addChoiceBtn.cloneNode(true);
        addChoiceBtn.parentNode.replaceChild(newAddChoiceBtn, addChoiceBtn);
        newAddChoiceBtn.addEventListener('click', () => addChoiceToModal(allSceneIds));

        const closeModal = () => {
            overlay.style.display = 'none';
        };
        cancelBtn.onclick = closeModal;
        closeBtn.onclick = closeModal;
        overlay.onclick = (e) => { if (e.target === overlay) closeModal(); };

        overlay.style.display = 'flex';
    }

    function renderModalChoices(choices, allSceneIds) {
        const container = document.getElementById('modal-choices-container');
        container.innerHTML = '';

        (choices || []).forEach((choice, index) => {
            const choiceEl = document.createElement('div');
            choiceEl.className = 'choice-item';

            const textInputHTML = `
                <div class="form-group">
                    <label for="choice-text-${index}">Текст выбора</label>
                    <input type="text" id="choice-text-${index}" value="${(choice.text || '').replace(/"/g, '&quot;')}">
                </div>`;

            const sceneOptions = allSceneIds.map(id =>
                `<option value="${id}" ${id === choice.next_scene ? 'selected' : ''}>${id}</option>`
            ).join('');

            const nextSceneSelectHTML = `
                <div class="form-group">
                    <label for="choice-next-${index}">Следующая сцена</label>
                    <select id="choice-next-${index}">${sceneOptions}</select>
                </div>`;

            const deleteBtnHTML = `
                <div class="choice-item-actions">
                    <button title="Удалить выбор" data-index="${index}">&times;</button>
                </div>`;

            choiceEl.innerHTML = textInputHTML + nextSceneSelectHTML + deleteBtnHTML;

            choiceEl.querySelector('button').addEventListener('click', (e) => {
                e.target.closest('.choice-item').remove();
            });

            container.appendChild(choiceEl);
        });
    }

    function addChoiceToModal(allSceneIds) {
        const currentChoices = getChoicesFromModal();
        currentChoices.push({ text: 'Новый выбор', next_scene: allSceneIds[0] || '' });
        renderModalChoices(currentChoices, allSceneIds);
    }

    function getChoicesFromModal() {
        const choices = [];
        const container = document.getElementById('modal-choices-container');
        const choiceItems = container.querySelectorAll('.choice-item');
        choiceItems.forEach((item, index) => {
            const textInput = item.querySelector(`#choice-text-${index}`);
            const nextSceneSelect = item.querySelector(`#choice-next-${index}`);
            if (textInput && nextSceneSelect) {
                const text = textInput.value.trim();
                const next_scene = nextSceneSelect.value;
                choices.push({ text, next_scene });
            }
        });
        return choices;
    }

    function saveSceneFromModal() {
        const questData = getCurrentQuestData();
        if (!questData) return;

        const originalId = document.getElementById('modal-scene-id-original').value;
        const newId = document.getElementById('modal-scene-id').value.trim();
        const newText = document.getElementById('modal-scene-text').value.trim();
        const sceneIdError = document.getElementById('scene-id-error');
        
        if (!newId) {
            sceneIdError.textContent = "ID сцены не может быть пустым.";
            sceneIdError.style.display = 'block';
            return;
        }
        if (newId !== originalId && questData.scenes.some(s => s.scene_id === newId)) {
            sceneIdError.textContent = "Этот ID уже используется. Выберите другой.";
            sceneIdError.style.display = 'block';
            return;
        }
        sceneIdError.style.display = 'none';

        const scene = questData.scenes.find(s => s.scene_id === originalId);
        if (scene) {
            scene.scene_id = newId;
            scene.text = newText;
            scene.choices = getChoicesFromModal();
        }

        if (newId !== originalId) {
            questData.scenes.forEach(s => {
                (s.choices || []).forEach(c => {
                    if (c.next_scene === originalId) c.next_scene = newId;
                });
            });
            if (questData.start_scene === originalId) questData.start_scene = newId;
        }

        saveQuestData(questData);
        document.getElementById('edit-modal-overlay').style.display = 'none';
    }

    function deleteScene(sceneId) {
        if (!confirm(`Вы уверены, что хотите удалить сцену "${sceneId}"? Это действие необратимо и удалит все переходы к этой сцене.`)) return;

        const questData = getCurrentQuestData();
        if (!questData) return;

        questData.scenes = questData.scenes.filter(s => s.scene_id !== sceneId);

        questData.scenes.forEach(s => {
            if (s.choices) s.choices = s.choices.filter(c => c.next_scene !== sceneId);
        });

        if (questData.start_scene === sceneId) {
            const newStartScene = questData.scenes.length > 0 ? questData.scenes[0].scene_id : '';
            questData.start_scene = newStartScene;
            if (newStartScene) {
                alert(`Стартовая сцена была удалена. Новой стартовой сценой назначена "${newStartScene}".`);
            } else {
                alert(`Стартовая сцена была удалена. В квесте не осталось сцен.`);
            }
        }

        saveQuestData(questData);
        document.getElementById('edit-modal-overlay').style.display = 'none';
    }

    function addScene() {
        let questData = getCurrentQuestData();

        if (!questData) {
            const newId = 'start_scene';
            questData = {
                quest_name: "Новый квест",
                start_scene: newId,
                scenes: [{ scene_id: newId, text: "Это первая сцена вашего нового квеста.", choices: [] }]
            };
        } else {
            const newId = `new_scene_${Date.now()}`;
            questData.scenes.push({ scene_id: newId, text: "Новая сцена. Отредактируйте ее.", choices: [] });
        }

        saveQuestData(questData);
    }

    function toggleEditMode() {
        editMode = !editMode;

        const editIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M0 0h24v24H0V0z" fill="none"></path><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"></path></svg>`;
        const doneIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M0 0h24v24H0V0z" fill="none"></path><path d="M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z"></path></svg>`;

        if (editMode) {
            editGraphBtn.innerHTML = doneIcon;
            editGraphBtn.title = "Завершить редактирование";
            graphEditorPanel.style.display = 'flex';
            jsonTab.style.display = 'none';
        } else {
            editGraphBtn.innerHTML = editIcon;
            editGraphBtn.title = "Редактировать граф";
            graphEditorPanel.style.display = 'none';
            jsonTab.style.display = 'block';
        }

        const currentResult = window.activeChatId && window.chats[window.activeChatId]?.result;
        if (currentResult && !currentResult.includes('Здесь появится')) {
            renderQuestGraph(currentResult);
        }
    }

    // ==================== ОСТАЛЬНАЯ ЛОГИКА ПРИЛОЖЕНИЯ ====================

    function debouncedSaveChats() {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(saveChats, 500);
    }

    function applyTheme(theme) {
        const oldTheme = document.documentElement.getAttribute('data-theme');
        let newTheme = theme;

        if (theme === 'system') {
            newTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', theme);
        
        if (oldTheme !== newTheme && window.activeChatId && window.chats[window.activeChatId]) {
            renderQuestGraph(window.chats[window.activeChatId].result);
        }
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
            const deleteIconSVG = `<svg xmlns="http://www.w3.org/2000/svg" height="18px" viewBox="0 0 24 24" width="18px" fill="currentColor"><path d="M0 0h24v24H0V0z" fill="none"/><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>`;
            deleteBtn.innerHTML = deleteIconSVG;
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
        renderQuestGraph(chat.result); 
        renderChatList();
        saveChats();
    }

    function createNewChat() {
        const newChatId = `chat_${Date.now()}`;
        const initialResult = 'Здесь появится сгенерированный JSON...';
        window.chats[newChatId] = {
            id: newChatId,
            title: `Новый чат ${Object.keys(window.chats).length + 1}`,
            setting: '',
            result: initialResult
        };
        graphBox.innerHTML = 'Здесь появится граф квеста...';
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

    // ==================== ЗАПУСК ИНИЦИАЛИЗАЦИИ И ПРИВЯЗКА СОБЫТИЙ ====================

    editGraphBtn.addEventListener('click', toggleEditMode);
    addSceneBtn.addEventListener('click', addScene);
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
    
    function showTab(tabName) {
        if (tabName === 'graph') {
            graphTab.classList.add('active');
            jsonTab.classList.remove('active');
            graphBox.style.display = 'block';
            resultBoxWrapper.style.display = 'none';

            // КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: ПОВТОРНАЯ ОТРИСОВКА
            // Если в чате есть валидный результат, перерисовываем граф.
            // Это исправляет его размеры, если он был создан в невидимом контейнере.
            const currentResult = window.activeChatId && window.chats[window.activeChatId]?.result;
            if (currentResult && !currentResult.includes('Здесь появится')) {
                console.log("Re-rendering graph on tab click to fix dimensions.");
                renderQuestGraph(currentResult);
            }
        } else { // 'json'
            jsonTab.classList.add('active');
            graphTab.classList.remove('active');
            graphBox.style.display = 'none';
            resultBoxWrapper.style.display = 'block';
        }
    }

    graphTab.addEventListener('click', () => showTab('graph'));
    jsonTab.addEventListener('click', () => showTab('json'));



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
        graphBox.innerHTML = '<p>Генерация... Пожалуйста, подождите.</p>';
        generateBtn.disabled = true;
        window.chats[window.activeChatId].setting = setting;
        
        showTab('graph');

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
            
            if (response.ok) {
                await renderQuestGraph(resultText);
            } else {
                graphBox.innerHTML = `<p class="status-error">${data.error || 'Неизвестная ошибка сервера'}</p>`;
            }

        } catch (error) {
            console.error('Fetch Error:', error);
            const errorMsg = 'Сетевая ошибка или не удалось обработать запрос.';
            resultBox.textContent = errorMsg;
            graphBox.innerHTML = `<p class="status-error">${errorMsg}</p>`;
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
    graphTab.click();
});

window.addEventListener('download-finished', (e) => {
    const { status, message } = e.detail;
    if (status !== 'cancelled') {
        alert(`Загрузка завершена!\nСтатус: ${status}\nСообщение: ${message}`);
    }
});