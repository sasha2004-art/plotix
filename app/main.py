import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request


from .models.recommended_models import RECOMMENDED_MODELS
from .services.quest_generator import (
    create_quest_from_setting,
    delete_local_models,
    get_available_models,
    validate_api_key,
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

    quest_json = create_quest_from_setting(setting, api_key, api_provider, model)

    if "error" in quest_json:
        return jsonify(quest_json), 500

    return jsonify(quest_json)


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
