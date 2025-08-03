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
    
    const editModeCheckbox = document.getElementById('edit-mode-checkbox');
    const contextMenu = document.getElementById('graph-context-menu');
    let isEditMode = false;
    let currentContextMenuData = {};


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
    
    // ==================== ЛОГИКА КОНТЕКСТНОГО МЕНЮ ====================

    function showContextMenu({ x, y, type, targetId, edgeData }) {
        currentContextMenuData = { type, targetId, edgeData };
        contextMenu.style.top = `${y}px`;
        contextMenu.style.left = `${x}px`;
        contextMenu.style.display = 'block';
        contextMenu.querySelectorAll('.context-menu-item, hr').forEach(item => item.classList.add('hidden'));

        if (type === 'node') {
            contextMenu.querySelectorAll('.node-action').forEach(item => item.classList.remove('hidden'));
        } else if (type === 'edge') {
            contextMenu.querySelectorAll('.edge-action, .edge-action-separator').forEach(item => item.classList.remove('hidden'));
        } else if (type === 'graph') {
            contextMenu.querySelectorAll('.graph-action, .graph-action-separator').forEach(item => item.classList.remove('hidden'));
        }
    }

    function hideContextMenu() {
        contextMenu.style.display = 'none';
        currentContextMenuData = {};
    }

    // ==================== Функции-редакторы данных ====================

    function getCurrentQuestData() {
        try {
            return JSON.parse(window.chats[window.activeChatId].result);
        } catch(e) {
            alert("Ошибка: не удалось прочитать данные квеста. Возможно, JSON поврежден.");
            console.error("Failed to parse quest data:", e);
            return null;
        }
    }

    function updateQuestData(newData) {
        const newResultString = JSON.stringify(newData, null, 2);
        window.chats[window.activeChatId].result = newResultString;
        resultBox.textContent = newResultString;
        renderQuestGraph(newResultString);
        debouncedSaveChats();
    }
    
    function editNode(nodeId) {
        let data = getCurrentQuestData();
        if (!data) return;
        const scene = data.scenes.find(s => s.scene_id === nodeId);
        if (!scene) {
            alert(`Внутренняя ошибка: не удалось найти узел с ID "${nodeId}"`);
            return;
        }

        const newText = prompt("Введите новый текст для узла (описание):", scene.text);
        if (newText !== null) {
            scene.text = newText;
            updateQuestData(data);
        }
    }
    
    function deleteNode(nodeId) {
        let data = getCurrentQuestData();
        if (!data) return;
        if (data.start_scene === nodeId) {
            alert("Нельзя удалить стартовый узел!"); return;
        }
        if (data.scenes.length <= 1) {
            alert("Нельзя удалить последний узел в квесте!"); return;
        }
        if (!confirm(`Вы уверены, что хотите удалить узел "${nodeId}" и все связанные с ним переходы?`)) {
            return;
        }

        data.scenes = data.scenes.filter(s => s.scene_id !== nodeId);
        data.scenes.forEach(s => {
            if (s.choices && Array.isArray(s.choices)) {
                s.choices = s.choices.filter(c => c.next_scene !== nodeId);
            }
        });
        updateQuestData(data);
    }

    function addNode() {
        let data = getCurrentQuestData();
        if (!data) return;
        let newId = prompt("Введите уникальный ID для нового узла:", `scene_${data.scenes.length + 1}`);
        if (!newId || !(newId = newId.trim())) return;

        while (data.scenes.some(s => s.scene_id === newId)) {
            newId = prompt(`ID "${newId}" уже существует. Введите другой ID:`);
            if (!newId || !(newId = newId.trim())) return;
        }

        data.scenes.push({ scene_id: newId, text: "Новый узел. Отредактируйте его.", choices: [] });
        updateQuestData(data);
    }
    
    function addEdge(fromNodeId) {
        let data = getCurrentQuestData();
        if (!data) return;
        const fromScene = data.scenes.find(s => s.scene_id === fromNodeId);
        if (!fromScene) {
            alert(`Внутренняя ошибка: не удалось найти узел-источник с ID "${fromNodeId}"`); return;
        }
        
        const existingNodeIds = data.scenes.map(s => s.scene_id).join(', ');
        const toNodeId = prompt(`Введите ID узла, к которому ведет переход:\n(Доступные: ${existingNodeIds})`);
        if (!toNodeId || !data.scenes.some(s => s.scene_id === toNodeId.trim())) {
            alert("Неверный или несуществующий ID узла."); return;
        }

        const text = prompt("Введите текст для этого выбора:");
        if (text === null) return;

        if (!Array.isArray(fromScene.choices)) fromScene.choices = [];
        fromScene.choices.push({ text: text, next_scene: toNodeId.trim() });
        updateQuestData(data);
    }

    function editEdge({ from, choiceIndex }) {
        let data = getCurrentQuestData();
        if (!data) return;
        const scene = data.scenes.find(s => s.scene_id === from);
        if (!scene || !scene.choices || !scene.choices[choiceIndex]) {
            alert("Внутренняя ошибка: не удалось найти редактируемое ребро."); return;
        }
        const choice = scene.choices[choiceIndex];

        const newText = prompt("Введите новый текст для ребра:", choice.text);
        if (newText !== null) {
            choice.text = newText;
            updateQuestData(data);
        }
    }

    function deleteEdge({ from, choiceIndex }) {
        if (!confirm("Вы уверены, что хотите удалить это ребро?")) return;
        let data = getCurrentQuestData();
        if (!data) return;
        const scene = data.scenes.find(s => s.scene_id === from);
        if (scene && scene.choices && scene.choices[choiceIndex]) {
            scene.choices.splice(choiceIndex, 1);
            updateQuestData(data);
        } else {
            alert("Внутренняя ошибка: не удалось найти удаляемое ребро.");
        }
    }

    // ==================== ЛОГИКА ГРАФА И РЕНДЕРИНГА (ИСПРАВЛЕНО) ====================
    
    function attachGraphEventListeners(edgeMap) {
        if (!isEditMode) return;
        const svg = graphBox.querySelector('svg');
        if (!svg) return;

        svg.addEventListener('contextmenu', (e) => {
            if (e.target === svg || e.target.closest('svg') === e.target) {
                e.preventDefault();
                showContextMenu({ x: e.clientX, y: e.clientY, type: 'graph' });
            }
        });

        // ИСПРАВЛЕНИЕ: Получаем ID напрямую из текстового содержимого узла
        graphBox.querySelectorAll('.node').forEach(nodeEl => {
            const textContent = nodeEl.textContent.trim();
            if (textContent) {
                nodeEl.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    showContextMenu({ x: e.clientX, y: e.clientY, type: 'node', targetId: textContent });
                });
            }
        });

        graphBox.querySelectorAll('.edgePath').forEach((edgeEl, index) => {
            const edgeData = edgeMap.get(index);
            if (edgeData) {
                edgeEl.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    showContextMenu({ x: e.clientX, y: e.clientY, type: 'edge', edgeData: edgeData });
                });
            }
        });
    }

    async function renderQuestGraph(jsonString) {
        graphBox.innerHTML = 'Подготовка графа...';
        await new Promise(resolve => setTimeout(resolve, 10));

        try {
            let questData;
            try { questData = JSON.parse(jsonString); } catch (e) { throw new Error("Invalid JSON format"); }
            if (!questData || !Array.isArray(questData.scenes) || !questData.start_scene) {
                throw new Error("Неверная структура JSON для графа.");
            }

            const sceneDataMap = new Map(questData.scenes.map(scene => [scene.scene_id, scene]));
            const allSceneIds = new Set(questData.scenes.map(s => s.scene_id));
            questData.scenes.forEach(scene => scene.choices?.forEach(c => c.next_scene && allSceneIds.add(c.next_scene)));
            
            const isDarkTheme = document.documentElement.getAttribute('data-theme') === 'dark';
            const themeVariables = { fontSize: '14px', primaryColor: isDarkTheme ? '#28252b' : '#ffffff', primaryTextColor: isDarkTheme ? '#ffffff' : '#000000', primaryBorderColor: isDarkTheme ? '#bfb8dd' : '#555555', lineColor: isDarkTheme ? '#bfb8dd' : '#555555', secondaryColor: '#715cd7', secondaryTextColor: '#ffffff', strokeWidth: '2px' };
            const formatText = (text = '', len = 20) => `"${text.replace(/"/g, '#quot;').split(' ').reduce((acc, word) => { let lastLine = acc[acc.length - 1]; if(lastLine && (lastLine.length + word.length + 1) < len) { acc[acc.length - 1] = `${lastLine} ${word}`; } else { acc.push(word); } return acc; }, []).join('<br>')}"`;
            
            let mermaidDefinition = `%%{init: {'theme': 'base', 'themeVariables': ${JSON.stringify(themeVariables)}}}%%\ngraph TD\n`;
            
            // ИСПРАВЛЕНИЕ: Определяем узлы с их реальными ID, Mermaid справится
            allSceneIds.forEach(id => {
                mermaidDefinition += `    ${id}["${id}"]\n`;
            });
            
            const edgeMap = new Map();
            let edgeCounter = 0;
            questData.scenes.forEach(scene => {
                if(Array.isArray(scene.choices)) {
                    scene.choices.forEach((choice, index) => {
                        if (choice && choice.next_scene) {
                            edgeMap.set(edgeCounter++, { from: scene.scene_id, choiceIndex: index });
                            mermaidDefinition += `    ${scene.scene_id} -->|${formatText(choice.text)}| ${choice.next_scene}\n`;
                        }
                    });
                }
            });
            
            mermaidDefinition += `    style ${questData.start_scene} fill:${themeVariables.secondaryColor},stroke:${themeVariables.secondaryColor},color:${themeVariables.secondaryTextColor},font-weight:bold\n`;
            
            graphBox.innerHTML = mermaidDefinition;
            graphBox.removeAttribute('data-processed');
            await mermaid.run({ nodes: [graphBox] });

            graphBox.querySelectorAll('.node').forEach(nodeEl => {
                const sceneId = nodeEl.textContent.trim();
                if (!sceneId) return;
                nodeEl.addEventListener('mousemove', (e) => {
                    tooltip.style.left = `${e.clientX + 15}px`;
                    tooltip.style.top = `${e.clientY + 15}px`;
                });
                nodeEl.addEventListener('mouseover', () => {
                    const sceneData = sceneDataMap.get(sceneId);
                    tooltip.innerHTML = sceneData ? `<strong>${sceneData.scene_id}</strong><hr style="margin: 5px 0; border-color: ${themeVariables.primaryBorderColor};"><p>${sceneData.text}</p>` : `<strong>${sceneId}</strong><hr style="margin: 5px 0; border-color: ${themeVariables.primaryBorderColor};"><p>Конец ветки.</p>`;
                    tooltip.style.display = 'block';
                });
                nodeEl.addEventListener('mouseout', () => { tooltip.style.display = 'none'; });
            });
            
            attachGraphEventListeners(edgeMap);

        } catch (error) {
            console.error("Ошибка рендеринга графа:", error);
            graphBox.innerHTML = `<p class="status-error">Не удалось построить граф. Проверьте валидность и структуру JSON.</p>`;
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
        if (theme === 'system') newTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
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
            if (id === window.activeChatId) chatDiv.classList.add('active');
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
                    saveChats(); renderChatList();
                }
            });
            const deleteBtn = document.createElement('button');
            deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" height="18px" viewBox="0 0 24 24" width="18px" fill="currentColor"><path d="M0 0h24v24H0V0z" fill="none"/><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>`;
            deleteBtn.classList.add('delete-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (confirm(`Вы уверены, что хотите удалить "${chat.title}"?`)) {
                    const idToDelete = id;
                    delete window.chats[idToDelete];
                    if (window.activeChatId === idToDelete) {
                        window.activeChatId = Object.keys(window.chats)[0] || null;
                        if (window.activeChatId) switchChat(window.activeChatId);
                        else createNewChat();
                    } else {
                        saveChats(); renderChatList();
                    }
                }
            });
            const chatActions = document.createElement('div');
            chatActions.classList.add('chat-actions');
            chatActions.appendChild(editBtn);
            chatActions.appendChild(deleteBtn);
            chatDiv.appendChild(chatActions);
            chatDiv.dataset.chatId = id;
            chatDiv.addEventListener('click', () => { switchChat(id); });
            chatList.appendChild(chatDiv);
        }
        if (chatIds.length > 8) {
            const toggleBtn = document.createElement('button');
            toggleBtn.textContent = chatsVisible ? 'Свернуть' : 'Развернуть';
            toggleBtn.addEventListener('click', () => {
                chatsVisible = !chatsVisible; renderChatList();
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
        const initialResult = JSON.stringify({ start_scene: "scene_1", scenes: [{ scene_id: "scene_1", text: "Это стартовая сцена. Включите 'Режим правки' и кликните правой кнопкой мыши, чтобы начать.", choices: [] }] }, null, 2);
        window.chats[newChatId] = { id: newChatId, title: `Новый чат ${Object.keys(window.chats).length + 1}`, setting: '', result: initialResult };
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
                        option.value = model.name; option.textContent = model.name; modelSelector.appendChild(option);
                    });
                    modelSelectorGroup.style.display = 'block';
                }
            } catch (error) { console.error('Error fetching local models:', error); }
            return;
        }
        if (selectedProvider === 'vps_proxy') {
        const groqModels = [
            "llama3-8b-8192",
            "llama3-70b-8192",
            "deepseek-r1-distill-llama-70b",
        ];
        const optgroup = document.createElement('optgroup');
        optgroup.label = "Доступно через прокси";
        groqModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            optgroup.appendChild(option);
        });
        modelSelector.appendChild(optgroup);
        modelSelectorGroup.style.display = 'block';
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
                    option.value = model; option.textContent = model; optgroup.appendChild(option);
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
            const response = await fetch('/api/models', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ api_provider: selectedProvider, api_key: apiKey }), });
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

    if (minimizeBtn) minimizeBtn.addEventListener('click', () => api.minimize());
    if (maximizeBtn) maximizeBtn.addEventListener('click', () => api.toggle_maximize());
    if (closeBtn) closeBtn.addEventListener('click', () => api.close());
    document.addEventListener('click', (e) => { if (!contextMenu.contains(e.target)) hideContextMenu(); });

    contextMenu.addEventListener('click', (e) => {
        const action = e.target.dataset.action;
        if (!action) return;
        const { type, targetId, edgeData } = currentContextMenuData;
        switch (action) {
            case 'edit-node': editNode(targetId); break;
            case 'delete-node': deleteNode(targetId); break;
            case 'add-edge': addEdge(targetId); break;
            case 'add-node': addNode(); break;
            case 'edit-edge': editEdge(edgeData); break;
            case 'delete-edge': deleteEdge(edgeData); break;
        }
        hideContextMenu();
    });

    if (sidebar) {
        sidebar.addEventListener('mouseenter', () => sidebar.classList.remove('collapsed'));
        sidebar.addEventListener('mouseleave', () => sidebar.classList.add('collapsed'));
    }

    newChatBtn.addEventListener('click', createNewChat);
    settingsBtn.addEventListener('click', () => { window.location.href = '/settings'; });
    settingInput.addEventListener('input', () => { if (window.activeChatId && window.chats[window.activeChatId]) { window.chats[window.activeChatId].setting = settingInput.value; debouncedSaveChats(); } });
    settingInput.addEventListener('blur', () => { clearTimeout(saveTimeout); saveChats(); });
    providerRadios.forEach(radio => radio.addEventListener('change', updateModels));
    editModeCheckbox.addEventListener('change', () => { isEditMode = editModeCheckbox.checked; graphBox.style.cursor = isEditMode ? 'context-menu' : 'default'; renderQuestGraph(window.chats[window.activeChatId].result); });

    function showTab(tabName) {
        hideContextMenu();
        if (tabName === 'graph') {
            graphTab.classList.add('active'); jsonTab.classList.remove('active');
            graphBox.style.display = 'block'; resultBoxWrapper.style.display = 'none';
            const currentResult = window.activeChatId && window.chats[window.activeChatId]?.result;
            if (currentResult && !currentResult.includes('Здесь появится')) renderQuestGraph(currentResult);
        } else {
            jsonTab.classList.add('active'); graphTab.classList.remove('active');
            graphBox.style.display = 'none'; resultBoxWrapper.style.display = 'block';
        }
    }

    graphTab.addEventListener('click', () => showTab('graph'));
    jsonTab.addEventListener('click', () => showTab('json'));

    downloadResultBtn.addEventListener('click', async () => {
        if (!window.activeChatId) return;
        const content = window.chats[window.activeChatId].result;
        try { JSON.parse(content); await api.save_quest_to_file(content); }
        catch (e) { alert('Невозможно скачать, так как результат не является валидным JSON.'); }
    });

    generateBtn.addEventListener('click', async () => {
        if (!window.activeChatId) createNewChat();
        const setting = settingInput.value.trim();
        const selectedProvider = document.querySelector('input[name="api_provider"]:checked').value;
        const selectedModel = modelSelector.value;
        const apiKey = localStorage.getItem(`${selectedProvider}_api_key`) || '';
        if (!setting || !selectedModel || (!apiKey && selectedProvider !== 'local' && selectedProvider !== 'vps_proxy')) {
            alert('Пожалуйста, введите сеттинг, выберите модель и убедитесь, что API ключ добавлен.'); return;
        }

        resultBox.textContent = 'Подключение к серверу...';
        graphBox.innerHTML = '<p>Подключение к серверу...</p>';
        generateBtn.disabled = true;
        window.chats[window.activeChatId].setting = setting;
        showTab('json'); 

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ setting, api_key: apiKey, api_provider: selectedProvider, model: selectedModel }),
            });
            
            if (!response.ok) {
                 const errorData = await response.json();
                 throw new Error(errorData.error || `Ошибка сервера: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let finalQuestData = null;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n').filter(line => line.trim() !== '');

                for (const line of lines) {
                    try {
                        const progressUpdate = JSON.parse(line);

                        if (progressUpdate.status === 'error') {
                            throw new Error(progressUpdate.message);
                        }

                        if (progressUpdate.message) {
                            resultBox.textContent = progressUpdate.message;
                            graphBox.innerHTML = `<p>${progressUpdate.message}</p>`;
                        }

                        if (progressUpdate.status === 'done' && progressUpdate.quest) {
                            finalQuestData = progressUpdate.quest;
                        }
                    } catch (e) {
                        console.error("Ошибка парсинга JSON-строки из потока:", line, e);
                    }
                }
            }

            if (finalQuestData) {
                const resultText = JSON.stringify(finalQuestData, null, 2);
                window.chats[window.activeChatId].result = resultText;
                resultBox.textContent = resultText;
                await renderQuestGraph(resultText);
                showTab('graph');
            } else {
                 throw new Error("Поток завершился без финального результата.");
            }

        } catch (error) {
            console.error('Fetch/Stream Error:', error);
            const errorMsg = `Ошибка: ${error.message}`;
            window.chats[window.activeChatId].result = errorMsg;
            resultBox.textContent = errorMsg;
            graphBox.innerHTML = `<p class="status-error">${errorMsg}</p>`;
            showTab('json');
        } finally {
            generateBtn.disabled = false;
            debouncedSaveChats();
        }
    });

    if (themeSelect) {
        const savedTheme = localStorage.getItem('theme') || 'system';
        themeSelect.value = savedTheme; applyTheme(savedTheme);
        themeSelect.addEventListener('change', (e) => applyTheme(e.target.value));
    } else { applyTheme(localStorage.getItem('theme') || 'system'); }
    
    await syncApiKeysFromFileToLocalStorage();
    await loadChats();
    if (window.activeChatId && window.chats[window.activeChatId]) switchChat(window.activeChatId);
    else if (Object.keys(window.chats).length > 0) switchChat(Object.keys(window.chats)[0]);
    else createNewChat();
    renderChatList(); updateModels(); showTab('graph');
});

// Глобальные обработчики событий pywebview
window.addEventListener('download-finished', (e) => { if (e.detail.status !== 'cancelled') alert(`Загрузка завершена!\nСтатус: ${e.detail.status}\nСообщение: ${e.detail.message}`); });
window.prepareForShutdown = async () => { try { if (typeof window.saveChats === "function") await window.saveChats(); } finally { if (window.pywebview && window.pywebview.api) window.pywebview.api.finalize_shutdown(); } };
function getActiveDownloads() { return JSON.parse(localStorage.getItem('activeDownloads')) || {}; }
function setActiveDownloads(d) { localStorage.setItem('activeDownloads', JSON.stringify(d)); }
window.startDownload = (repoId, filename) => { const d = getActiveDownloads(); d[`${repoId}/${filename}`] = { repo_id: repoId, filename, p: 0 }; setActiveDownloads(d); window.dispatchEvent(new CustomEvent('download-started', { detail: d[`${repoId}/${filename}`] })); };
window.updateDownloadProgress = (p) => { const d=getActiveDownloads(); d[`${p.repo_id}/${p.filename}`]=p; setActiveDownloads(d); window.dispatchEvent(new CustomEvent('download-progress', { detail: p })); };
window.finishDownload = (f) => { const d=getActiveDownloads(); delete d[`${f.repo_id}/${f.filename}`]; setActiveDownloads(d); window.dispatchEvent(new CustomEvent('download-finished', { detail: f })); };