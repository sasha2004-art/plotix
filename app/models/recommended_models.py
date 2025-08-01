RECOMMENDED_MODELS = {
    "low": [
        {
            # ИСПРАВЛЕНИЕ: Использование официального репозитория от Microsoft для GGUF
            "repo_id": "microsoft/Phi-3-mini-4k-instruct-gguf",
            "filename": "Phi-3-mini-4k-instruct-q4.gguf",
            "description": "Мощная модель от Microsoft, лучшая в своем классе (3.8B параметров). Отличное качество для своего размера.",
            "requirements": "≥ 4GB VRAM или ≥ 8GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: Использование официального репозитория от Google для GGUF
            "repo_id": "google/gemma-2b-it-gguf",
            "filename": "gemma-2b-it.Q4_K_M.gguf",
            "description": "Модель от Google (2B параметров), оптимизированная для диалогов и инструкций. Хорошая производительность.",
            "requirements": "≥ 3GB VRAM или ≥ 8GB RAM (для CPU)",
        },
        {
            "repo_id": "lmstudio-ai/stablelm-2-zephyr-1_6b-GGUF",
            "filename": "stablelm-2-zephyr-1_6b-Q4_K_M.gguf",
            "description": "Очень компактная (1.6B параметров), но способная модель. Идеальна для самых слабых систем.",
            "requirements": "≥ 2GB VRAM или ≥ 8GB RAM (для CPU)",
        },
    ],
    "medium": [
        {
            # ИСПРАВЛЕНИЕ: Использование проверенного репозитория от сообщества для Llama 3.1
            "repo_id": "bartowski/Llama-3.1-8B-Instruct-GGUF",
            "filename": "Llama-3.1-8B-Instruct-Q4_K_M.gguf",
            "description": "Новейшая state-of-the-art модель от Meta (8B параметров). Превосходное качество и производительность.",
            "requirements": "≥ 8GB VRAM или ≥ 16GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: Использование проверенного репозитория от сообщества для последней версии Mistral
            "repo_id": "dranger003/Mistral-7B-Instruct-v0.3-GGUF",
            "filename": "Mistral-7B-Instruct-v0.3.Q4_K_M.gguf",
            "description": "Обновленная модель от Mistral AI (7B параметров). Очень быстрая и до сих пор крайне эффективная.",
            "requirements": "≥ 6GB VRAM или ≥ 16GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: Указано корректное имя файла, которое существует в репозитории.
            "repo_id": "IlyaGusev/saiga_mistral_7b_gguf",
            "filename": "model-q4_K.gguf",
            "description": "Дообученная на русских данных Saiga на базе Mistral 7B. Может давать лучшие результаты для русскоязычных задач.",
            "requirements": "≥ 6GB VRAM или ≥ 16GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: Использование официального репозитория от Google для GGUF
            "repo_id": "google/gemma-7b-it-gguf",
            "filename": "gemma-7b-it.Q4_K_M.gguf",
            "description": "Версия Gemma на 7B параметров. Отличная альтернатива Llama и Mistral.",
            "requirements": "≥ 6GB VRAM или ≥ 16GB RAM (для CPU)",
        },
    ],
    "high": [
        {
            # ИСПРАВЛЕНИЕ: Использование официального репозитория от Mistral AI для GGUF
            "repo_id": "mistralai/Mixtral-8x7B-Instruct-v0.1-GGUF",
            "filename": "mixtral-8x7b-instruct-v0.1.Q4_K_M.gguf",
            "description": "Mixture-of-Experts (MoE) модель. Превосходное качество, близкое к GPT-3.5/4. Требовательна к ресурсам.",
            "requirements": "≥ 24GB VRAM или ≥ 48GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: Использование официального репозитория от NousResearch для GGUF
            "repo_id": "NousResearch/Nous-Hermes-2-Yi-34B-GGUF",
            "filename": "nous-hermes-2-yi-34b.Q4_K_M.gguf",
            "description": "Очень сильная модель на 34B параметров. Отличный выбор для тех, у кого много VRAM, но не хватает для 70B моделей.",
            "requirements": "≥ 24GB VRAM или ≥ 32GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: Использование проверенного репозитория от сообщества для Llama 3.1 70B
            "repo_id": "bartowski/Llama-3.1-70B-Instruct-GGUF",
            "filename": "Llama-3.1-70B-Instruct-Q3_K_M.gguf",
            "description": "Топовая модель от Meta (70B). Даже с низкой квантизацией (Q3_K_M) обеспечивает невероятное качество. Для энтузиастов.",
            "requirements": "≥ 32GB VRAM или ≥ 64GB RAM (для CPU)",
        },
    ],
}