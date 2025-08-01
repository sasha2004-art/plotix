import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import google.generativeai as genai
import openai
from groq import Groq

# --- ИЗМЕНЕНИЕ: Тестируемый импорт опциональной зависимости ---
try:
    from llama_cpp import Llama  # type: ignore[reportMissingImports]
except ImportError:
    Llama = None
# --- КОНЕЦ ИЗМЕНЕНИЯ ---

logger = logging.getLogger(__name__)


def _get_master_prompt(setting_text: str) -> str:
    """Генерирует основной промпт для LLM."""
    return f"""
  Ты — профессиональный геймдизайнер и сценарист. Твоя задача — создать структуру нелинейного квеста в формате JSON на основе предоставленного сеттинга.

  КЛЮЧЕВЫЕ ПРАВИЛА ГЕНЕРАЦИИ:
  1.  **ЯЗЫК:** Весь сгенерированный текст (в полях `text` и `choices.text`) ДОЛЖЕН БЫТЬ СТРОГО НА РУССКОМ ЯЗЫКЕ.
  2.  **КОЛИЧЕСТВО СЦЕН:** Сгенерируй от 5 до 10 сцен (объектов в массиве `scenes`).
  3.  **ВЕТВЛЕНИЕ:** В квесте должна быть как минимум одна развилка. Одна из побочных ветвей должна иметь глубину не менее 3 сцен, прежде чем она завершится или вернется в основной сюжет.
  4.  **ВЫБОРЫ:** Каждая сцена должна предлагать игроку как минимум 2 варианта выбора (`choices`).
  5.  **СТРУКТУРА JSON:** JSON должен быть строго валидным и следовать структуре, описанной ниже. `start_scene` должен указывать на `scene_id` одной из сцен.

  Вот требуемая структура JSON:
  {{
    "start_scene": "id_стартовой_сцены",
    "scenes": [
      {{
        "scene_id": "уникальный_текстовый_id_сцены",
        "text": "Полное описание ситуации, окружения и персонажей на русском языке. Это основной текст, который увидит игрок.",
        "choices": [
          {{
            "text": "Текст выбора для игрока на русском языке.",
            "next_scene": "scene_id_сцены_на_которую_ведет_этот_выбор"
          }},
          {{
            "text": "Второй вариант выбора для игрока на русском языке.",
            "next_scene": "scene_id_другой_сцены"
          }}
        ]
      }}
    ]
  }}

  Сеттинг для генерации:
  ---
  {setting_text}
  ---

  Теперь сгенерируй JSON для этого квеста, строго соблюдая все правила и структуру.
  """


def create_quest_from_setting(
    setting_text: str, api_key: str, api_provider: str, model: str
) -> Dict[str, Any]:
    """Генерирует квест, используя указанного API-провайдера."""
    master_prompt = _get_master_prompt(setting_text)
    response_content = None

    try:
        if api_provider == "groq":
            client = Groq(api_key=api_key)
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": master_prompt}],
                model=model,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            response_content = chat_completion.choices[0].message.content

        elif api_provider == "openai":
            client = openai.OpenAI(api_key=api_key)
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": master_prompt}],
                model=model,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            response_content = chat_completion.choices[0].message.content

        elif api_provider == "gemini":
            genai.configure(api_key=api_key)  # type: ignore[reportPrivateImportUsage]
            gemini_model = genai.GenerativeModel(model)  # type: ignore[reportPrivateImportUsage]
            response = gemini_model.generate_content(master_prompt)
            response_content = response.text

        elif api_provider == "local":
            if Llama is None:
                logger.error(
                    "Модуль llama_cpp не установлен. Пожалуйста, перезапустите установку с опцией 'y'."
                )
                return {"error": "Поддержка локальных LLM не установлена."}

            model_dir = os.getenv("LOCAL_MODEL_PATH", "quest-generator/models")
            model_path = os.path.join(model_dir, model)

            if not os.path.exists(model_path):
                error_msg = f"Локальная модель не найдена по пути: {model_path}"
                logger.error(error_msg)
                return {"error": error_msg}

            llm = Llama(
                model_path=model_path,
                n_ctx=4096,
                n_gpu_layers=-1,
                verbose=False,
                # ИЗМЕНЕНИЕ: TinyLlama и многие другие современные модели используют ChatML.
                # Это более универсальный и правильный формат для таких моделей.
                chat_format="chatml",
            )
            chat_completion = llm.create_chat_completion(
                messages=[{"role": "user", "content": master_prompt}],
                temperature=0.7,
                response_format={"type": "json_object"},
                stream=False,
            )
            response_content = chat_completion["choices"][0]["message"]["content"]

        else:
            logger.error(f"Unknown API provider: {api_provider}")
            return {"error": f"Unknown API provider: {api_provider}"}

        if response_content is None:
            logger.error("LLM returned no content.")
            return {"error": "LLM returned no content."}

        # Clean response content for markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_content)
        if json_match:
            cleaned_content = json_match.group(1)
        else:
            # If no markdown block found, assume the content is raw JSON
            cleaned_content = response_content

        try:
            parsed_json = json.loads(cleaned_content)
            # ИЗМЕНЕНИЕ: Проверка на пустой результат от модели (A4)
            if not parsed_json:
                logger.error(
                    f"LLM ({model}) returned an empty JSON object. "
                    f"Original content: '{response_content}'"
                )
                return {
                    "error": "Модель вернула пустой результат. "
                    "Это может случиться с небольшими моделями. "
                    "Попробуйте более мощную модель или измените сеттинг."
                }
            return parsed_json
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON from {api_provider} ({model}). "
                f"Raw content (original): '{response_content}'. "
                f"Cleaned content: '{cleaned_content}'. Error: {e}"
            )
            return {
                "error": "Модель не смогла сгенерировать валидный JSON. "
                "Попробуйте изменить сеттинг или выбрать другую модель/провайдера."
                " (Возможно, модель вернула неполный или некорректный JSON)"
            }

    except Exception as e:
        logger.error(
            f"An error occurred while generating quest with {api_provider}: {e}"
        )
        error_message_lower = str(e).lower()
        # Добавлена проверка на ошибку квоты
        if (
            "quota" in error_message_lower
            or "insufficient_quota" in error_message_lower
        ):
            return {
                "error": "Превышен лимит использования API или недостаточно средств. Пожалуйста, проверьте ваш тарифный план или баланс."
            }
        if "rate limit" in error_message_lower:
            return {"error": "Превышен лимит запросов к API. Попробуйте позже."}
        if (
            "authentication" in error_message_lower
            or "invalid api key" in error_message_lower
            or "401" in error_message_lower
        ):
            return {"error": "Неверный API ключ. Пожалуйста, проверьте ваш ключ."}
        if (
            "model not found" in error_message_lower
            or "model_not_found" in error_message_lower
            or "modelnotfounderror" in error_message_lower
            or "deprecated" in error_message_lower
            or ("404" in error_message_lower and "model" in error_message_lower)
        ):
            return {
                "error": f"Выбранная модель '{model}' не найдена, недоступна или устарела у провайдера {api_provider}. Попробуйте другую модель."
            }

        return {
            "error": f"Произошла ошибка при обращении к API {api_provider}: {str(e)}"
        }


def validate_api_key(api_provider: str, api_key: str) -> Dict[str, Any]:
    """Проверяет валидность API-ключа, делая легковесный запрос к провайдеру."""
    try:
        if api_provider == "groq":
            client = Groq(api_key=api_key)
            client.models.list()  # Простой запрос для проверки аутентификации
            return {"status": "ok"}
        elif api_provider == "openai":
            client = openai.OpenAI(api_key=api_key)
            client.models.list()
            return {"status": "ok"}
        elif api_provider == "gemini":
            genai.configure(api_key=api_key)  # type: ignore[reportPrivateImportUsage]
            # Проверяем, есть ли доступные модели для генерации текста
            models = [
                m
                for m in genai.list_models()  # type: ignore[reportPrivateImportUsage]
                if "generateContent" in m.supported_generation_methods
            ]
            if not models:
                raise ValueError("No generative models found for this API key.")
            return {"status": "ok"}
        elif api_provider == "local":
            # Для локальных моделей ключ не нужен, всегда считаем 'ok'
            return {"status": "ok"}
        else:
            return {
                "status": "error",
                "message": f"Unknown API provider: {api_provider}",
            }

    except Exception as e:
        logger.error(f"API key validation failed for {api_provider}: {e}")
        # Возвращаем более понятное сообщение об ошибке
        if "401" in str(e) or "invalid" in str(e).lower():
            return {"status": "error", "message": "Неверный API ключ."}
        return {
            "status": "error",
            "message": "Ошибка проверки ключа. См. логи сервера.",
        }


def get_available_models(api_provider: str, api_key: str) -> Dict[str, Any]:
    """Получает и фильтрует список доступных моделей."""
    try:
        # --- Local provider ---
        if api_provider == "local":
            model_dir_str = os.getenv("LOCAL_MODEL_PATH", "quest-generator/models")
            model_dir = Path(model_dir_str)
            models_info = []
            if not model_dir.is_dir():
                logger.warning(
                    f"Директория локальных моделей '{model_dir.resolve()}' не найдена."
                )
            else:
                for f in sorted(model_dir.glob("*.gguf")):
                    if f.is_file():
                        try:
                            models_info.append(
                                {"name": f.name, "size": f.stat().st_size}
                            )
                        except OSError as e:
                            logger.warning(
                                f"Не удалось получить информацию о файле {f}: {e}"
                            )
            return {"models": models_info}

        # --- Cloud providers ---
        models_list = []
        if api_provider == "groq":
            client = Groq(api_key=api_key)
            models = client.models.list().data
            models_list = [model.id for model in models]
        elif api_provider == "openai":
            client = openai.OpenAI(api_key=api_key)
            models = client.models.list().data
            models_list = [
                model.id
                for model in models
                if "gpt" in model.id.lower() or "text" in model.id.lower()
            ]
        elif api_provider == "gemini":
            genai.configure(api_key=api_key)  # type: ignore[reportPrivateImportUsage]
            models = [
                m.name
                for m in genai.list_models()  # type: ignore[reportPrivateImportUsage]
                if "generateContent" in m.supported_generation_methods
            ]
            models_list = models
        else:
            return {"error": f"Unknown API provider: {api_provider}"}

        # Post-processing for cloud models
        unique_models = {}
        for model in sorted(models_list):
            base_name = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model)
            base_name = re.sub(r"-\d{4}$", "", base_name)
            if base_name not in unique_models:
                unique_models[base_name] = model
        return {"models": list(unique_models.values())}

    except Exception as e:
        logger.error(f"Failed to get models for {api_provider}: {e}")
        return {"error": str(e)}


def delete_local_models(filenames: List[str]) -> Dict[str, Any]:
    """
    Удаляет указанные файлы локальных моделей из директории.
    Производит проверку для предотвращения удаления файлов вне целевой директории.
    """
    model_dir_str = os.getenv("LOCAL_MODEL_PATH", "quest-generator/models")
    model_dir = Path(model_dir_str)
    deleted_files = []
    errors = []

    if not model_dir.is_dir():
        return {"status": "error", "message": "Директория с моделями не найдена."}

    for filename in filenames:
        # Security check: prevent path traversal attacks
        if filename != Path(filename).name or not filename.endswith(".gguf"):
            errors.append(f"Некорректное имя файла: {filename}")
            continue

        file_path = model_dir / filename
        try:
            if file_path.is_file():
                file_path.unlink()
                deleted_files.append(filename)
                logger.info(f"Successfully deleted local model: {filename}")
            else:
                errors.append(f"Файл не найден или не является файлом: {filename}")
        except Exception as e:
            error_msg = f"Ошибка при удалении {filename}: {e}"
            errors.append(error_msg)
            logger.error(error_msg)

    message_parts = []
    if deleted_files:
        message_parts.append(f"Успешно удалено: {len(deleted_files)} файл(ов).")
    if errors:
        message_parts.append(f"Ошибки: {len(errors)}. {'; '.join(errors)}")

    final_message = (
        " ".join(message_parts) if message_parts else "Файлы не были выбраны."
    )
    status = "ok" if not errors else "error"

    return {"status": status, "message": final_message}
