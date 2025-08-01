RECOMMENDED_MODELS = {
    "low": [
        {
            "repo_id": "microsoft/Phi-3-mini-4k-instruct-gguf",
            "filename": "Phi-3-mini-4k-instruct-q4.gguf",
            "description": "Мощная модель от Microsoft, лучшая в своем классе (3.8B параметров). Отличное качество для своего размера.",
            "requirements": "≥ 4GB VRAM или ≥ 8GB RAM (для CPU)",
        },
        {
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
            "repo_id": "meta-llama/Llama-3-8B-Instruct-GGUF",
            "filename": "Meta-Llama-3-8B-Instruct-Q4_K_M.gguf",
            "description": "State-of-the-art модель от Meta (8B параметров). Считается одной из лучших в своем размере.",
            "requirements": "≥ 8GB VRAM или ≥ 16GB RAM (для CPU)",
        },
        {
            "repo_id": "mistralai/Mistral-7B-Instruct-v0.2-GGUF",
            "filename": "mistral-7b-instruct-v0.2.Q4_K_M.gguf",
            "description": "Классическая модель от Mistral AI (7B параметров). Очень быстрая и до сих пор крайне эффективная.",
            "requirements": "≥ 6GB VRAM или ≥ 16GB RAM (для CPU)",
        },
        {
            "repo_id": "IlyaGusev/saiga_mistral_7b_gguf",
            "filename": "model-q4_K.gguf",
            "description": "Дообученная на русских данных Saiga на базе Mistral 7B. Может давать лучшие результаты для русскоязычных задач.",
            "requirements": "≥ 6GB VRAM или ≥ 16GB RAM (для CPU)",
        },
        {
            "repo_id": "google/gemma-7b-it-gguf",
            "filename": "gemma-7b-it.Q4_K_M.gguf",
            "description": "Версия Gemma на 7B параметров. Отличная альтернатива Llama и Mistral.",
            "requirements": "≥ 6GB VRAM или ≥ 16GB RAM (для CPU)",
        },
    ],
    "high": [
        {
            "repo_id": "mistralai/Mixtral-8x7B-Instruct-v0.1-GGUF",
            "filename": "mixtral-8x7b-instruct-v0.1.Q4_K_M.gguf",
            "description": "Mixture-of-Experts (MoE) модель. Превосходное качество, близкое к GPT-3.5/4. Требовательна к ресурсам.",
            "requirements": "≥ 24GB VRAM или ≥ 48GB RAM (для CPU)",
        },
        {
            "repo_id": "NousResearch/Nous-Hermes-2-Yi-34B-GGUF",
            # ИСПРАВЛЕНИЕ: Указано корректное имя файла, которое существует в репозитории.
            "filename": "nous-hermes-2-yi-34b.Q5_K_M.gguf",
            "description": "Очень сильная модель на 34B параметров. Отличный выбор для тех, у кого много VRAM, но не хватает для 70B моделей.",
            "requirements": "≥ 24GB VRAM или ≥ 32GB RAM (для CPU)",
        },
        {
            "repo_id": "meta-llama/Llama-3-70B-Instruct-GGUF",
            "filename": "Meta-Llama-3-70B-Instruct.Q3_K_M.gguf",
            "description": "Топовая модель от Meta. Даже с низкой квантизацией (Q3_K_M) обеспечивает невероятное качество. Для энтузиастов.",
            "requirements": "≥ 32GB VRAM или ≥ 64GB RAM (для CPU)",
        },
    ],
}
