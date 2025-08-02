RECOMMENDED_MODELS = {
    "low": [
        {
            # ИСПРАВЛЕНИЕ : ✅
            "repo_id": "microsoft/Phi-3-mini-4k-instruct-gguf",
            "filename": "Phi-3-mini-4k-instruct-q4.gguf",
            "description": "Мощная модель от Microsoft, лучшая в своем классе (3.8B параметров). Отличное качество для своего размера.",
            "requirements": "≥ 4GB VRAM или ≥ 8GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: ✅
            "repo_id": "google/gemma-2b-it-gguf",
            "filename": "gemma-2b-it.gguf",
            "description": "Модель от Google (2B параметров), оптимизированная для диалогов и инструкций. Хорошая производительность.",
            "requirements": "≥ 3GB VRAM или ≥ 8GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: ✅
            "repo_id": "stabilityai/stablelm-2-zephyr-1_6b",
            "filename": "stablelm-2-zephyr-1_6b.gguf",
            "description": "Официальная GGUF-версия компактной (1.6B параметров), но способной модели. Идеальна для самых слабых систем.",
            "requirements": "≥ 2GB VRAM или ≥ 8GB RAM (для CPU)",
        },
    ],
    "medium": [
        {
            # ИСПРАВЛЕНИЕ: ✅
            "repo_id": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
            "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_L.gguf",
            "description": "Новейшая state-of-the-art модель от Meta (8B параметров). Превосходное качество и производительность.",
            "requirements": "≥ 8GB VRAM или ≥ 16GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: ✅
            "repo_id": "MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF",
            "filename": "Mistral-7B-Instruct-v0.3.fp16.gguf",
            "description": "Обновленная модель от Mistral AI (7B параметров). Очень быстрая и до сих пор крайне эффективная.",
            "requirements": "≥ 6GB VRAM или ≥ 16GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: ✅
            "repo_id": "IlyaGusev/saiga_mistral_7b_gguf",
            "filename": "model-q4_K.gguf",
            "description": "Дообученная на русских данных Saiga на базе Mistral 7B. Может давать лучшие результаты для русскоязычных задач.",
            "requirements": "≥ 6GB VRAM или ≥ 16GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: ✅
            "repo_id": "google/gemma-7b-it-gguf",
            "filename": "gemma-7b-it.gguf",
            "description": "Версия Gemma на 7B параметров. Отличная альтернатива Llama и Mistral.",
            "requirements": "≥ 6GB VRAM или ≥ 16GB RAM (для CPU)",
        },
    ],
    "high": [
        {
            # ИСПРАВЛЕНИЕ: ❌
            "repo_id": "TheBloke/Mixtral-8x7B-Instruct-v0.1-GGUF",
            "filename": "mixtral-8x7b-instruct-v0.1.Q8_0.gguf",
            "description": "Mixture-of-Experts (MoE) модель от TheBloke. Максимальное качество (Q8_0), требует много ресурсов.",
            "requirements": "≥ 48GB VRAM или ≥ 64GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ: ❌
            "repo_id": "NousResearch/Nous-Hermes-2-Yi-34B-GGUF",
            "filename": "Nous-Hermes-2-Yi-34B.Q8_0.gguf",
            "description": "Очень сильная модель на 34B параметров в максимальном качестве (Q8_0).",
            "requirements": "≥ 36GB VRAM или ≥ 48GB RAM (для CPU)",
        },
        {
            # ИСПРАВЛЕНИЕ:❌
            "repo_id": "bartowski/Meta-Llama-3.1-70B-Instruct-GGUF",
            "filename": "Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf",
            "description": "Топовая модель от Meta (70B) с хорошей квантизацией Q4_K_M. Невероятное качество для энтузиастов.",
            "requirements": "≥ 48GB VRAM или ≥ 64GB RAM (для CPU)",
        },
    ],
}
