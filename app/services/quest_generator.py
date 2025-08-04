import json
import logging
import os
import re
import time # <--- ДОБАВЛЕНО
import requests
from pathlib import Path
from typing import Any, Dict, List, Iterator, Set

import google.generativeai as genai
import openai
from groq import Groq, APIStatusError # <--- ИЗМЕНЕНО

try:
    from llama_cpp import Llama  # type: ignore[reportMissingImports]
except ImportError:
    Llama = None

logger = logging.getLogger(__name__)


# ЭТАП 1: ПРОМПТ ДЛЯ "ГЕЙМДИЗАЙНЕРА"
def _get_plot_concept_prompt(
    setting_text: str, scene_count: int, tone: str, pacing: str, narrative_elements: list[str]
) -> str:
    """Генерирует высокоуровневый концепт сюжета с учетом параметров от 'Режиссера'."""
    
    narrative_elements_map = {
        "moral_dilemma": "Моральная дилемма (сложный выбор без очевидно правильного ответа)",
        "unreliable_npc": "Ненадежный NPC (персонаж, который лжет или имеет скрытые мотивы)",
        "false_trail": "Ложный след / 'Красная селедка' (ветка расследования, уводящая в тупик)",
        "multiple_endings": "Наличие нескольких концовок (действия игрока приводят к разным финалам)"
    }
    
    known_elements_desc = []
    custom_elements_text = []
    
    for element in narrative_elements:
        if element in narrative_elements_map:
            known_elements_desc.append(narrative_elements_map[element])
        else:
            custom_elements_text.append(element)

    known_part = ""
    if known_elements_desc:
        known_part = f"- **Обязательные нарративные техники:** {'; '.join(known_elements_desc)}."

    custom_part = ""
    if custom_elements_text:
        custom_part = f"- **Обязательные уникальные события (заданы пользователем):** {'; '.join(custom_elements_text)}."

    return f"""
            Ты — эксперт-геймдизайнер, известный своими глубокими и нелинейными сюжетами. Твоя задача — написать краткий, но увлекательный концепт для квеста, строго следуя заданным параметрам. Опиши его как связный рассказ.

            **ПАРАМЕТРЫ ОТ РЕЖИССЕРА:**
            - **Общее количество сцен:** Постарайся уложиться примерно в {scene_count} ключевых сцен.
            - **Желаемый тон:** {tone if tone else 'Нейтральный'}.
            - **Темп повествования:** {pacing if pacing else 'Средний'}.
            {known_part}
            {custom_part}

            **ТРЕБОВАНИЯ К КОНЦЕПТУ:**
            1.  **Формат:** Обычный текст, не JSON.
            2.  **Содержание:** На основе сеттинга и параметров выше, опиши завязку, ключевые этапы, персонажей и их мотивы.

            **Сеттинг для квеста:**
            ---
            {setting_text}
            ---
            Теперь напиши связный и логичный концепт сюжета, который позже ляжет в основу структуры квеста, строго следуя ПАРАМЕТРАМ ОТ РЕЖИССЕРА.
            """


# ЭТАП 2: ПРОМПТ ДЛЯ "АРХИТЕКТОРА" (ИЗВЛЕЧЕНИЕ ПРОСТОГО ТЕКСТОВОГО СПИСКА)
def _get_scene_list_from_concept_prompt(plot_concept: str) -> str:
    """Извлекает из текстового концепта ПРОСТОЙ нумерованный список сцен."""
    return f"""
Ты — технический ассистент. Твоя задача — внимательно прочитать готовый концепт сюжета и извлечь из него список ключевых игровых ситуаций в виде простого нумерованного списка.

**ГОТОВЫЙ КОНЦЕПТ СЮЖЕТА:**
---
{plot_concept}
---

**ТВОЯ ЗАДАЧА:**
Выпиши все ключевые игровые ситуации из концепта в виде нумерованного списка. Каждая строка — одна ситуация.

**КЛЮЧЕВЫЕ ПРАВИЛА:**
1.  **ФОРМАТ:** Простой нумерованный список. Никакого JSON.
2.  **Содержание:** Краткое описание игровой ситуации на русском языке.

**Пример вывода:**
1. Игрок прибывает в джаз-клуб и осматривает место происшествия.
2. Игрок допрашивает напуганного бармена.
3. Игрок находит загадочную записку в гримерке.

Теперь извлеки все ключевые игровые ситуации из предоставленного концепта и представь их в виде простого списка.
"""


# ЭТАП 3: ПРОМПТ ДЛЯ "РЕЖИССЁРА"
def _get_graph_from_scenes_prompt(scene_list_json: str) -> str:
    """Создает полный JSON-скелет, добавляя связи и выборы к плоскому списку сцен."""
    return f"""
Ты — геймдизайнер-нарративщик. Тебе дан список игровых ситуаций. Твоя задача — связать их в логичный, нелинейный квест.
**СПИСОК ИГРОВЫХ СИТУАЦИЙ (СЦЕН):**
---
{scene_list_json}
---
**ТВОЯ ЗАДАЧА:**
Доработай этот JSON, превратив его в полноценный квестовый граф. Для этого:
1.  Определи, какая сцена должна быть стартовой, и добавь корневой ключ `"start_scene"`.
2.  Для КАЖДОЙ сцены добавь поле `"choices"`.
3.  В поле `"choices"` создай 2-3 варианта выбора для игрока. Каждый выбор должен быть объектом с полями:
    - `"choice_summary"`: Краткое описание ДЕЙСТВИЯ игрока (например, "Обыскать стол").
    - `"next_scene"`: `scene_id` сцены, к которой приведет этот выбор.
**КЛЮЧЕВЫЕ ПРАВИЛА:**
- **Логика:** Связи должны быть логичными и соответствовать описаниям сцен.
- **Нелинейность:** Создай хотя бы одну развилку.
- **ЗАПРЕТ ЦИКЛОВ (КРИТИЧЕСКИ ВАЖНО):** Сюжет должен всегда двигаться ВПЕРЕД. Создай строго ациклический граф (DAG). Возвраты в пройденные сцены категорически запрещены.
Верни ПОЛНЫЙ и готовый JSON-скелет квеста.
"""


# ЭТАП 4: ПРОМПТ ДЛЯ "СЦЕНАРИСТА"
def _get_scene_detail_prompt(
    setting_text: str, scene_summary: str, history_choice: str, previous_scene_text: str
) -> str:
    # ... (без изменений)
    previous_scene_block = (f'ПРЕДЫДУЩАЯ СИТУАЦИЯ (ПОЛНЫЙ ТЕКСТ):\n---\n{previous_scene_text}\n---\n' if previous_scene_text else "Это стартовая ситуация квеста.")
    return f"""
Ты — талантливый сценарист интерактивных историй. Твоя задача — описать игровую ситуацию для ИГРОКА, продолжая повествование.
ОБЩИЙ СЕТТИНГ КВЕСТА:
{setting_text}
{previous_scene_block}
КОНТЕКСТ ПЕРЕХОДА (ДЕЙСТВИЕ ИГРОКА, КОТОРОЕ ПРИВЕЛО СЮДА):
{history_choice}
КРАТКОЕ ОПИСАНИЕ ТЕКУЩЕЙ ИГРОВОЙ СИТУАЦИИ:
"{scene_summary}"
ТВОЯ ЗАДАЧА:
Напиши текст для этой ситуации (`text`) и варианты выбора (`choices_text`) с точки зрения ИГРОКА.
КЛЮЧЕВЫЕ ПРАВИЛА:
1.  **ПРАВИЛО ИГРОКА-ПРОТАГОНИСТА:** Пиши так, чтобы игрок чувствовал себя главным героем. Используй обороты "Вы видите...", "Вам предстоит решить...".
2.  **ДИНАМИКА:** Сосредоточься на действиях, диалогах и доступных игроку возможностях.
3.  **ЯЗЫК И ЧИСТОТА:** Текст должен быть СТРОГО на РУССКОМ ЯЗЫКЕ. Не используй ни единого слова или символа из других языков.
4.  **СТРУКТУРА JSON:** Верни ТОЛЬКО ОДИН JSON-объект.
    {{
      "text": "Полное описание ситуации с точки зрения игрока.",
      "choices_text": ["Текст первого действия, доступного игроку.", "Текст второго действия, доступного игроку."]
    }}
Теперь, основываясь на всем контексте, сгенерируй JSON с детализацией для ТЕКУЩЕЙ игровой ситуации.
"""


# ЭТАП 6: ПРОМПТ ДЛЯ "КОРРЕКТОРА"
def _get_correction_prompt(quest_json_str: str) -> str:
    """Создает промпт для финальной вычитки и исправления языковых артефактов."""
    return f"""
Ты — педантичный редактор-корректор. Твоя единственная задача — вычитать предоставленный JSON и исправить в нем все иноязычные вкрапления и опечатки.
**ПРАВИЛА КОРРЕКТУРЫ:**
1.  **ТОЛЬКО ЯЗЫК:** Исправляй только слова на латинице, странные символы или опечатки в русских словах.
2.  **НЕ ТРОГАЙ СЮЖЕТ:** Не меняй смысл предложений, имена, названия или структуру сюжета.
3.  **СОХРАНИ СТРУКТУРУ:** Верни абсолютно идентичный по структуре JSON.
**Пример исправления:**
- **Было:** `{{"text": "Вы видите, как он tries to escape, оставляя странный символ 不断."}}`
- **Стало:** `{{"text": "Вы видите, как он пытается сбежать, оставляя странный символ."}}`
**JSON для вычитки:**
---
{quest_json_str}
---
Теперь верни исправленный, чистый и валидный JSON.
"""


def _call_llm(prompt: str, api_provider: str, api_key: str, model: str, force_text_response: bool = False) -> str:
    max_retries = 3
    delay = 1.0  # начальная задержка в секундах

    for attempt in range(max_retries):
        try:
            response_content = None
            response_format_option = {"type": "text"} if force_text_response else {"type": "json_object"}
            if api_provider == "groq":
                client = Groq(api_key=api_key)
                chat_completion = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model=model, temperature=0.7, response_format=response_format_option)
                response_content = chat_completion.choices[0].message.content
            elif api_provider == "openai":
                client = openai.OpenAI(api_key=api_key)
                chat_completion = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model=model, temperature=0.7, response_format=response_format_option)
                response_content = chat_completion.choices[0].message.content
            elif api_provider == "gemini":
                genai.configure(api_key=api_key)
                gemini_model = genai.GenerativeModel(model)
                response = gemini_model.generate_content(prompt)
                response_content = response.text
            elif api_provider == "local":
                if Llama is None: raise ImportError("Модуль llama_cpp не установлен.")
                model_dir, model_path = os.getenv("LOCAL_MODEL_PATH", "quest-generator/models"), os.path.join(model_dir, model)
                if not os.path.exists(model_path): raise FileNotFoundError(f"Локальная модель не найдена по пути: {model_path}")
                llm = Llama(model_path=model_path, n_ctx=4096, n_gpu_layers=-1, verbose=False, chat_format="chatml")
                chat_completion = llm.create_chat_completion(messages=[{"role": "user", "content": prompt}], temperature=0.7, response_format=response_format_option, stream=False)
                response_content = chat_completion["choices"][0]["message"]["content"]
            elif api_provider == "vps_proxy":
                proxy_url = "http://91.184.253.216:5001/proxy/generate"
                payload = {"prompt": prompt, "model": model}
                logger.info(f"Отправка запроса на VPS прокси: {proxy_url}")
                response = requests.post(proxy_url, json=payload, timeout=120)
                response.raise_for_status()
                response_content = response.text
            else:
                raise ValueError(f"Unknown API provider: {api_provider}")

            if response_content is None: raise ValueError("LLM returned no content.")
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_content)
            return json_match.group(1) if json_match else response_content

        except (APIStatusError, openai.APIStatusError, requests.exceptions.HTTPError) as e:
            status_code = -1
            if hasattr(e, 'status_code'):
                status_code = e.status_code
            elif hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                status_code = e.response.status_code

            is_retryable = status_code == 429 or status_code >= 500

            if is_retryable and attempt < max_retries - 1:
                logger.warning(
                    f"API вернуло ошибку {status_code}. Повторная попытка через {delay:.1f} сек... (Попытка {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
                delay *= 2  # Экспоненциальная задержка
                continue
            else:
                logger.error(f"Не удалось выполнить запрос к API после {attempt + 1} попыток или ошибка не является временной.")
                raise e  # Перевыбрасываем исключение, если все попытки исчерпаны
        except Exception as e:
             logger.error(f"Произошла непредвиденная ошибка при вызове LLM: {e}")
             raise e


# ЭТАП 5: "ЦЕНЗОР" (ФИНАЛЬНАЯ ВАЛИДАЦИЯ)
def _validate_and_clean_quest(quest_json: Dict[str, Any]) -> Dict[str, Any]:
    # ... (без изменений)
    if "scenes" not in quest_json or not quest_json["scenes"]: return quest_json
    all_scene_ids = {scene["scene_id"] for scene in quest_json["scenes"]}
    reachable_ids: Set[str] = set()
    queue = [quest_json.get("start_scene")]
    while queue:
        current_id = queue.pop(0)
        if current_id and current_id in all_scene_ids and current_id not in reachable_ids:
            reachable_ids.add(current_id)
            current_scene = next((s for s in quest_json["scenes"] if s["scene_id"] == current_id), None)
            if current_scene:
                for choice in current_scene.get("choices", []):
                    next_id = choice.get("next_scene")
                    if next_id: queue.append(next_id)
    unreachable_ids = all_scene_ids - reachable_ids
    if unreachable_ids:
        logger.warning(f"Обнаружены и будут удалены недостижимые сцены: {unreachable_ids}")
        quest_json["scenes"] = [scene for scene in quest_json["scenes"] if scene["scene_id"] in reachable_ids]
        for scene in quest_json["scenes"]:
            if "choices" in scene:
                scene["choices"] = [c for c in scene["choices"] if c.get("next_scene") in reachable_ids]
    return quest_json


# ГЛАВНАЯ ФУНКЦИЯ-ОРКЕСТРАТОР
def create_quest_from_setting(
    setting_text: str, api_key: str, api_provider: str, model: str,
    scene_count: int, tone: str, pacing: str, narrative_elements: List[str]
) -> Iterator[str]:
    """Генерирует квест, управляя многоэтапным конвейером 'Студия Разработки'."""
    try:
        # Этап 1: Геймдизайнер
        yield json.dumps({"status": "concept", "message": "1/6: Геймдизайнер придумывает концепт..."})
        concept_prompt = _get_plot_concept_prompt(
            setting_text, scene_count, tone, pacing, narrative_elements
        )
        plot_concept = _call_llm(concept_prompt, api_provider, api_key, model, force_text_response=True)
        time.sleep(1) # Пауза между запросами

        # Этап 2: Архитектор
        yield json.dumps({"status": "architect", "message": "2/6: Архитектор извлекает ключевые сцены..."})
        scene_list_prompt = _get_scene_list_from_concept_prompt(plot_concept)
        scene_list_text = _call_llm(scene_list_prompt, api_provider, api_key, model, force_text_response=True)
        time.sleep(1) # Пауза между запросами
        
        # ЭТАП 2.5: Python-парсер
        scenes_for_graph = []
        for i, line in enumerate(scene_list_text.strip().split('\n')):
            clean_line = re.sub(r'^\d+\.\s*', '', line).strip()
            if clean_line:
                # Генерируем простой ID, чтобы избежать ошибок LLM
                scene_id = f"scene_{i+1}"
                scenes_for_graph.append({"scene_id": scene_id, "summary": clean_line})
        if not scenes_for_graph:
            raise ValueError("Архитектор не смог извлечь ни одной сцены из концепта.")
        scene_list_json = json.dumps(scenes_for_graph, ensure_ascii=False, indent=2)

        # Этап 3: Режиссёр
        yield json.dumps({"status": "director", "message": "3/6: Режиссёр выстраивает связи и выборы..."})
        graph_prompt = _get_graph_from_scenes_prompt(scene_list_json)
        skeleton_str = _call_llm(graph_prompt, api_provider, api_key, model, force_text_response=False)
        time.sleep(1) # Пауза между запросами
        skeleton_json = json.loads(skeleton_str)
        if "scenes" not in skeleton_json or "start_scene" not in skeleton_json:
            raise ValueError("Режиссёр не смог создать корректную структуру из списка сцен.")

        # Этап 4: Сценарист
        final_quest = skeleton_json.copy()
        # ... (логика детализации без изменений)
        scene_map, parent_map = {s['scene_id']: s for s in final_quest['scenes']}, {}
        for scene in final_quest['scenes']:
            for choice in scene.get('choices', []):
                if 'next_scene' in choice: parent_map[choice['next_scene']] = { "parent_id": scene['scene_id'], "choice_summary": choice.get('choice_summary', '...')}
        for i, scene_to_detail in enumerate(final_quest["scenes"]):
            scene_id, summary = scene_to_detail["scene_id"], scene_to_detail.get("summary", "Нет описания.")
            yield json.dumps({ "status": "detailing_scene", "message": f'4/6: Сценарист пишет текст для сцены {i + 1}/{len(final_quest["scenes"])}...'})
            history_choice, previous_scene_text = f"Это стартовая ситуация: '{summary}'.", ""
            parent_info = parent_map.get(scene_id)
            if parent_info:
                parent_id, choice_summary = parent_info['parent_id'], parent_info['choice_summary']
                parent_scene_data = scene_map.get(parent_id)
                if parent_scene_data and 'text' in parent_scene_data: previous_scene_text = parent_scene_data['text']
                history_choice = f"Вы решили: '{choice_summary}'. Это привело вас к следующей ситуации: '{summary}'."
            detail_prompt = _get_scene_detail_prompt(setting_text, summary, history_choice, previous_scene_text)
            detailed_str = _call_llm(detail_prompt, api_provider, api_key, model, force_text_response=False)
            if i < len(final_quest["scenes"]) -1: time.sleep(1) # Пауза между запросами
            detailed_json = json.loads(detailed_str)
            scene_to_detail["text"] = detailed_json.get("text", "Описание не было сгенерировано.")
            scene_map[scene_id]["text"] = scene_to_detail["text"]
            detailed_choices_text = detailed_json.get("choices_text", [])
            for choice_idx, choice in enumerate(scene_to_detail.get("choices", [])):
                choice["text"] = detailed_choices_text[choice_idx] if choice_idx < len(detailed_choices_text) else choice.get("choice_summary", "...")
                choice.pop("choice_summary", None)
            scene_to_detail.pop("summary", None)

        # Этап 5: Цензор
        yield json.dumps({"status": "validating", "message": "5/6: Цензор проверяет структуру..."})
        cleaned_quest = _validate_and_clean_quest(final_quest)
        
        # Этап 6: Корректор
        yield json.dumps({"status": "correcting", "message": "6/6: Корректор вычитывает текст..."})
        quest_to_correct_str = json.dumps(cleaned_quest, ensure_ascii=False, indent=2)
        correction_prompt = _get_correction_prompt(quest_to_correct_str)
        corrected_quest_str = _call_llm(correction_prompt, api_provider, api_key, model, force_text_response=False)
        final_quest_json = json.loads(corrected_quest_str)

        yield json.dumps({"status": "done", "quest": final_quest_json})

    except Exception as e:
        logger.error(f"Ошибка в многоэтапной генерации: {e}", exc_info=True)
        # ... (обработка ошибок)
        error_message_lower = str(e).lower()
        error_map = { "quota": "Превышен лимит API.", "insufficient_quota": "Превышен лимит API.", "invalid api key": "Неверный API ключ.", "401": "Неверный API ключ.", "429": "Превышен лимит запросов к API. Попробуйте позже."}
        for key, msg in error_map.items():
            if key in error_message_lower:
                error_payload = {"error": msg}; break
        else:
            error_payload = {"error": f"Произошла ошибка на сервере: {str(e)}"}
        yield json.dumps({"status": "error", "message": error_payload["error"]})


def validate_api_key(api_provider: str, api_key: str) -> Dict[str, Any]:
    # ... (без изменений)
    try:
        if api_provider == "groq":
            client = Groq(api_key=api_key); client.models.list()
            return {"status": "ok"}
        elif api_provider == "openai":
            client = openai.OpenAI(api_key=api_key); client.models.list()
            return {"status": "ok"}
        elif api_provider == "gemini":
            genai.configure(api_key=api_key)
            models = [m for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
            if not models: raise ValueError("No generative models found for this API key.")
            return {"status": "ok"}
        elif api_provider == "local":
            return {"status": "ok"}
        else:
            return {"error": f"Unknown API provider: {api_provider}"}
    except Exception as e:
        logger.error(f"API key validation failed for {api_provider}: {e}")
        if "401" in str(e) or "invalid" in str(e).lower():
            return {"status": "error", "message": "Неверный API ключ."}
        return {"status": "error", "message": "Ошибка проверки ключа. См. логи сервера."}


def get_available_models(api_provider: str, api_key: str) -> Dict[str, Any]:
    # ... (без изменений)
    try:
        if api_provider == "local":
            model_dir_str = os.getenv("LOCAL_MODEL_PATH", "quest-generator/models")
            model_dir = Path(model_dir_str)
            models_info = []
            if model_dir.is_dir():
                for f in model_dir.glob("*.gguf"):
                    if f.is_file():
                        try: models_info.append({"name": f.name, "size": f.stat().st_size})
                        except OSError as e: logger.warning(f"Не удалось получить информацию о файле {f.name}: {e}")
            models_info.sort(key=lambda x: x["name"])
            return {"models": models_info}

        models_list = []
        if api_provider == "groq":
            client = Groq(api_key=api_key)
            models = client.models.list().data
            models_list = [model.id for model in models]
        elif api_provider == "openai":
            client = openai.OpenAI(api_key=api_key)
            models = client.models.list().data
            models_list = [model.id for model in models if "gpt" in model.id.lower() or "text" in model.id.lower()]
        elif api_provider == "gemini":
            genai.configure(api_key=api_key)
            models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
            models_list = [m.replace("models/", "") for m in models]
        else:
            return {"error": f"Unknown API provider: {api_provider}"}

        unique_models_map = {}
        for model in sorted(models_list):
            base_name = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model)
            base_name = re.sub(r"-\d{4}$", "", base_name)
            if base_name not in unique_models_map: unique_models_map[base_name] = model
        
        unique_models_list = list(unique_models_map.values())
        categorized_models: Dict[str, List[str]] = {"free": [], "paid": []}
        FREE_KEYWORDS_GEMINI, FREE_KEYWORDS_OPENAI = ["flash", "1.0-pro"], ["gpt-3.5-turbo"]
        for model_name in unique_models_list:
            is_free = False
            if api_provider == "groq": is_free = True
            elif api_provider == "gemini":
                if any(keyword in model_name for keyword in FREE_KEYWORDS_GEMINI): is_free = True
            elif api_provider == "openai":
                if any(keyword in model_name for keyword in FREE_KEYWORDS_OPENAI): is_free = True
            if is_free: categorized_models["free"].append(model_name)
            else: categorized_models["paid"].append(model_name)
        return categorized_models
    except Exception as e:
        logger.error(f"Failed to get models for {api_provider}: {e}")
        return {"error": str(e)}


def delete_local_models(filenames: List[str]) -> Dict[str, Any]:
    # ... (без изменений)
    model_dir_str = os.getenv("LOCAL_MODEL_PATH", "quest-generator/models")
    model_dir = Path(model_dir_str)
    deleted_files, errors = [], []
    if not model_dir.is_dir(): return {"status": "error", "message": "Директория с моделями не найдена."}
    for filename in filenames:
        if filename != Path(filename).name or not filename.endswith(".gguf"):
            errors.append(f"Некорректное имя файла: {filename}"); continue
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
    status = "ok"
    if deleted_files: message_parts.append(f"Успешно удалено: {len(deleted_files)} файл(ов).")
    if errors:
        message_parts.append(f"Ошибки: {len(errors)}. {'; '.join(errors)}")
        status = "partial" if deleted_files else "error"
    final_message = " ".join(message_parts) if message_parts else "Файлы не были выбраны."
    return {"status": status, "message": final_message}