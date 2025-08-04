import logging
import os
import json # Добавлен
import re # Добавлен

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, Response, stream_with_context


from .models.recommended_models import RECOMMENDED_MODELS
from .services.quest_generator import (
    create_quest_from_setting,
    delete_local_models,
    get_available_models,
    validate_api_key,
    # Новые импорты для тестового режима
    _get_plot_concept_prompt,
    _get_scene_list_from_concept_prompt,
    _get_graph_from_scenes_prompt,
    _get_scene_detail_prompt,
    _get_correction_prompt,
    _validate_and_clean_quest,
)

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")

# Определяем, включены ли локальные LLM
USE_LOCAL_LLM = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"

if __name__ != "__main__":
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)


@app.route("/")
def index():
    # Передаем флаг в шаблон
    return render_template("index.html", use_local_llm=USE_LOCAL_LLM)


@app.route("/settings")
def settings():
    # Передаем флаг в шаблон
    return render_template("settings.html", use_local_llm=USE_LOCAL_LLM)


@app.route("/generate", methods=["POST"])
def generate_quest_endpoint():
    data = request.get_json()
    if (
        not data
        or "setting" not in data
        or "api_key" not in data
        or "api_provider" not in data
        or "model" not in data
    ):
        return (
            jsonify(
                {
                    "error": "Missing 'setting', 'api_key', 'api_provider' or 'model' in request body"
                }
            ),
            400,
        )

    setting = data["setting"]
    api_key = data["api_key"]
    api_provider = data["api_provider"]
    model = data["model"]
    scene_count = data.get("scene_count", 8)
    tone = data.get("tone", "")
    pacing = data.get("pacing", "")
    narrative_elements = data.get("narrative_elements", [])

    def generate_stream():
        """Оборачивает генератор квестов для потоковой передачи."""
        quest_generator = create_quest_from_setting(
            setting, api_key, api_provider, model,
            scene_count, tone, pacing, narrative_elements
        )
        for progress_update in quest_generator:
            yield progress_update + '\n'


    # Используем mimetype 'application/x-ndjson' для потоковой передачи JSON, разделенного новой строкой
    return Response(stream_with_context(generate_stream()), mimetype='application/x-ndjson')


@app.route("/validate_api_key", methods=["POST"])
def validate_api_key_endpoint():
    data = request.get_json()
    if not data or "api_key" not in data or "api_provider" not in data:
        return jsonify({"error": "Missing 'api_key' or 'api_provider'"}), 400

    api_key = data["api_key"]
    api_provider = data["api_provider"]

    if not api_key:
        return jsonify({"status": "error", "message": "API ключ не может быть пустым."})

    result = validate_api_key(api_provider=api_provider, api_key=api_key)

    return jsonify(result)


@app.route("/api/models", methods=["POST"])
def available_models_endpoint():
    data = request.get_json()
    if not data or "api_key" not in data or "api_provider" not in data:
        return jsonify({"error": "Missing 'api_key' or 'api_provider'"}), 400

    api_key = data["api_key"]
    api_provider = data["api_provider"]

    if not api_key and api_provider != "local":
        return jsonify({"error": "API ключ не может быть пустым."})

    models = get_available_models(api_provider=api_provider, api_key=api_key)

    return jsonify(models)


@app.route("/api/recommended_models", methods=["GET"])
def recommended_models_endpoint():
    return jsonify(RECOMMENDED_MODELS)


@app.route("/api/local_models", methods=["GET"])
def get_local_models():
    """Возвращает список локальных моделей GGUF, делегируя сервисному слою."""
    # ИЗМЕНЕНИЕ: Делегируем получение моделей сервисному слою для консистентности (A3)
    # Ключ API не используется для локальных моделей, передаем пустую строку.
    result = get_available_models(api_provider="local", api_key="")
    if "error" in result:
        # get_available_models для local теперь не должен возвращать ошибку,
        # но для надежности оставим проверку.
        return jsonify(result), 500
    return jsonify(result)


@app.route("/api/local_models/delete", methods=["POST"])
def delete_local_models_endpoint():
    """Удаляет указанные файлы локальных моделей."""
    data = request.get_json()
    if not data or "filenames" not in data or not isinstance(data["filenames"], list):
        return jsonify({"error": "Требуется 'filenames' в виде списка."}), 400

    result = delete_local_models(filenames=data["filenames"])

    status_code = 200
    if result.get("status") == "error":
        status_code = 500
    elif result.get("status") == "partial":
        status_code = 207  # Multi-Status

    return jsonify(result), status_code


@app.route("/test/get_prompt", methods=["POST"])
def get_test_prompt_endpoint():
    """
    Управляет пошаговой генерацией промптов для тестового/ручного режима.
    Принимает текущее состояние и возвращает промпт для следующего шага.
    """
    data = request.get_json()
    if not data or "step" not in data or "state" not in data:
        return jsonify({"error": "Неверный формат запроса для тестового режима."}), 400

    step = data["step"]
    state = data["state"]
    prompt = ""

    try:
        if step == "concept":
            prompt = _get_plot_concept_prompt(
                state.get("setting", ""),
                state.get("scene_count", 8),
                state.get("tone", ""),
                state.get("pacing", ""),
                state.get("narrative_elements", []),
            )
            return jsonify({"prompt": prompt, "next_step": "architect"})

        elif step == "architect":
            prompt = _get_scene_list_from_concept_prompt(
                state.get("concept_response", "")
            )
            return jsonify({"prompt": prompt, "next_step": "director"})

        elif step == "director":
            scene_list_text = state.get("architect_response", "")
            # Этап 2.5: Python-парсер
            scenes_for_graph = []
            for i, line in enumerate(scene_list_text.strip().split("\n")):
                clean_line = re.sub(r"^\d+\.\s*", '', line).strip()
                if clean_line:
                    scene_id = f"scene_{i+1}"
                    scenes_for_graph.append({"scene_id": scene_id, "summary": clean_line})

            if not scenes_for_graph:
                 return jsonify({"error": "Не удалось извлечь ни одной сцены из ответа архитектора."}), 400

            scene_list_json = json.dumps(scenes_for_graph, ensure_ascii=False, indent=2)
            prompt = _get_graph_from_scenes_prompt(scene_list_json)
            return jsonify({"prompt": prompt, "next_step": "detailing"})

        elif step == "detailing":
            skeleton_json = state.get("skeleton_json", {})

            # --- НОРМАЛИЗАЦИЯ: Преобразуем 'scenes' из объекта в массив, если это необходимо ---
            if isinstance(skeleton_json.get("scenes"), dict):
                app.logger.warning("Converting 'scenes' from dict to list in detailing step.")
                converted_scenes = []
                # Итерируем по элементам словаря и добавляем их в список
                for scene_id, scene_data in skeleton_json["scenes"].items():
                    if not isinstance(scene_data, dict):
                        app.logger.warning(f"Unexpected scene data format for {scene_id}: {scene_data}")
                        continue
                    # Убедимся, что scene_id присутствует в самом объекте сцены
                    if "scene_id" not in scene_data:
                        scene_data["scene_id"] = scene_id
                    converted_scenes.append(scene_data)
                skeleton_json["scenes"] = converted_scenes
            # --- КОНЕЦ НОРМАЛИЗАЦИИ ---

            scenes_list = skeleton_json.get("scenes", [])
            scene_index = state.get("scene_index_to_detail", 0)

            # Проверка на пустой список или выход за границы
            if not scenes_list or scene_index >= len(scenes_list):
                app.logger.error(f"Attempted to detail scene {scene_index} but scenes list is empty or index is out of bounds.")
                return jsonify({"error": "Внутренняя ошибка: Нет сцен для детализации или неверный индекс."}), 400

            scene_to_detail = scenes_list[scene_index]

            scene_map = {s['scene_id']: s for s in scenes_list} # Используем scenes_list после возможной нормализации
            parent_map = {}
            for scene in scenes_list: # Используем scenes_list
                for choice in scene.get('choices', []):
                    if 'next_scene' in choice: parent_map[choice['next_scene']] = { "parent_id": scene['scene_id'], "choice_summary": choice.get('choice_summary', '...')}

            summary = scene_to_detail.get("summary", "Нет описания.")
            history_choice, previous_scene_text = f"Это стартовая ситуация: '{summary}'.", ""
            parent_info = parent_map.get(scene_to_detail["scene_id"])

            if parent_info:
                parent_id = parent_info['parent_id']
                choice_summary = parent_info['choice_summary']
                parent_scene_data = scene_map.get(parent_id)
                if parent_scene_data and 'text' in parent_scene_data:
                    previous_scene_text = parent_scene_data['text']
                history_choice = f"Вы решили: '{choice_summary}'. Это привело вас к следующей ситуации: '{summary}'."

            prompt = _get_scene_detail_prompt(
                state.get("setting", ""),
                summary,
                history_choice,
                previous_scene_text,
            )
            return jsonify({"prompt": prompt, "next_step": "detailing"}) # Всегда возвращаем detailing, пока не кончатся сцены

        elif step == "correcting":
            quest_json_str = json.dumps(state.get("final_quest", {}), ensure_ascii=False, indent=2)
            prompt = _get_correction_prompt(quest_json_str)
            return jsonify({"prompt": prompt, "next_step": "done"})

        else:
            return jsonify({"error": f"Неизвестный шаг: {step}"}), 400

    except Exception as e:
        app.logger.error(f"Ошибка в тестовом режиме на шаге {step}: {e}", exc_info=True)
        return jsonify({"error": f"Ошибка на сервере: {e}"}), 500