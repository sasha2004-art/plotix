from unittest.mock import MagicMock, patch

from app.services.quest_generator import (
    create_quest_from_setting,
    validate_api_key,
    get_available_models,
)


@patch("app.services.quest_generator.Groq")
def test_create_quest_groq_success(mock_groq):
    """Тестирует успешный путь с провайдером Groq."""
    mock_response_content = '{"questTitle": "Успешный тест Groq"}'
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = mock_response_content
    mock_groq.return_value.chat.completions.create.return_value = mock_completion
    result = create_quest_from_setting(
        "любой сеттинг", "fake_key", "groq", "llama3-88b-8192"
    )
    assert result == {"questTitle": "Успешный тест Groq"}
    mock_groq.return_value.chat.completions.create.assert_called_once()


@patch("app.services.quest_generator.openai.OpenAI")
def test_create_quest_openai_success(mock_openai):
    """Тестирует успешный путь с провайдером OpenAI."""
    mock_response_content = '{"questTitle": "Успешный тест OpenAI"}'
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = mock_response_content
    mock_openai.return_value.chat.completions.create.return_value = mock_completion
    result = create_quest_from_setting("любой сеттинг", "fake_key", "openai", "gpt-4")
    assert result == {"questTitle": "Успешный тест OpenAI"}
    mock_openai.return_value.chat.completions.create.assert_called_once()


@patch("app.services.quest_generator.genai")
def test_create_quest_gemini_success(mock_genai):
    """Тестирует успешный путь с провайдером Gemini."""
    mock_response = MagicMock()
    mock_response.text = '{"questTitle": "Успешный тест Gemini"}'
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model
    result = create_quest_from_setting(
        "любой сеттинг", "fake_key", "gemini", "gemini-pro"
    )
    assert result == {"questTitle": "Успешный тест Gemini"}
    mock_genai.configure.assert_called_once_with(api_key="fake_key")


@patch("app.services.quest_generator.Groq")
def test_create_quest_api_error(mock_groq):
    """Тестирует случай, когда API (на примере Groq) возвращает ошибку."""
    mock_groq.return_value.chat.completions.create.side_effect = Exception("API Error")
    result = create_quest_from_setting(
        "любой сеттинг", "fake_key", "groq", "llama3-8b-8192"
    )
    assert "error" in result
    assert "Произошла ошибка при обращении к API groq: API Error" in result["error"]


@patch("app.services.quest_generator.Groq")
def test_create_quest_no_content(mock_groq):
    """Тестирует случай, когда API (на примере Groq) не вернуло контент."""
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = None
    mock_groq.return_value.chat.completions.create.return_value = mock_completion
    result = create_quest_from_setting(
        "любой сеттинг", "fake_key", "groq", "llama3-8b-8192"
    )
    assert "error" in result
    assert result["error"] == "LLM returned no content."


@patch("app.services.quest_generator.Groq")
def test_validate_key_groq_success(mock_groq):
    """Тестирует успешную валидацию ключа Groq."""
    mock_groq.return_value.models.list.return_value = MagicMock()
    assert validate_api_key("groq", "valid") == {"status": "ok"}


@patch("app.services.quest_generator.openai.OpenAI")
def test_validate_key_openai_success(mock_openai):
    """Тестирует успешную валидацию ключа OpenAI."""
    mock_openai.return_value.models.list.return_value = MagicMock()
    assert validate_api_key("openai", "valid") == {"status": "ok"}


@patch("app.services.quest_generator.genai")
def test_validate_key_gemini_success(mock_genai):
    """Тестирует успешную валидацию ключа Gemini."""
    mock_model = MagicMock()
    mock_model.supported_generation_methods = ["generateContent"]
    mock_genai.list_models.return_value = [mock_model]
    assert validate_api_key("gemini", "valid") == {"status": "ok"}
    mock_genai.configure.assert_called_once_with(api_key="valid")


@patch("app.services.quest_generator.genai")
def test_validate_key_gemini_no_models(mock_genai):
    """Тестирует валидацию Gemini, когда не найдено подходящих моделей."""
    mock_genai.list_models.return_value = []
    result = validate_api_key("gemini", "no-models-key")
    assert result["status"] == "error"
    assert "Ошибка проверки ключа" in result["message"]


@patch("app.services.quest_generator.Groq")
def test_validate_key_api_error_401(mock_groq):
    """Тестирует обработку ошибки 401 (неверный ключ)."""
    mock_groq.return_value.models.list.side_effect = Exception("401 Invalid Key")
    result = validate_api_key("groq", "invalid")
    assert result == {"status": "error", "message": "Неверный API ключ."}


@patch("app.services.quest_generator.Groq")
def test_validate_key_generic_api_error(mock_groq):
    """Тестирует обработку общей ошибки API."""
    mock_groq.return_value.models.list.side_effect = Exception("Connection Timeout")
    result = validate_api_key("groq", "bad-connection")
    assert result == {
        "status": "error",
        "message": "Ошибка проверки ключа. См. логи сервера.",
    }


def test_validate_key_unknown_provider():
    """Тестирует валидацию с неизвестным провайдером."""
    result = validate_api_key("foobar", "any_key")
    assert result == {"error": "Unknown API provider: foobar"}


@patch("app.services.quest_generator.Groq")
def test_get_available_models_groq_success(mock_groq):
    """Тестирует успешное получение моделей от Groq."""
    mock_model = MagicMock()
    mock_model.id = "llama3-8b-8192"
    mock_groq.return_value.models.list.return_value.data = [mock_model]
    result = get_available_models("groq", "fake_key")
    assert result == {"models": ["llama3-8b-8192"]}


@patch("app.services.quest_generator.openai.OpenAI")
def test_get_available_models_openai_success(mock_openai):
    """Тестирует успешное получение моделей от OpenAI."""
    mock_model = MagicMock()
    mock_model.id = "gpt-4"
    mock_openai.return_value.models.list.return_value.data = [mock_model]
    result = get_available_models("openai", "fake_key")
    assert result == {"models": ["gpt-4"]}


@patch("app.services.quest_generator.genai")
def test_get_available_models_gemini_success(mock_genai):
    """Тестирует успешное получение моделей от Gemini."""
    mock_model = MagicMock()
    mock_model.name = "gemini-pro"
    mock_model.supported_generation_methods = ["generateContent"]
    mock_genai.list_models.return_value = [mock_model]
    result = get_available_models("gemini", "fake_key")
    assert result == {"models": ["gemini-pro"]}


def test_get_available_models_unknown_provider():
    """Тестирует получение моделей от неизвестного провайдера."""
    result = get_available_models("foobar", "any_key")
    assert result == {"error": "Unknown API provider: foobar"}


@patch("app.services.quest_generator.Groq")
def test_get_available_models_api_error(mock_groq):
    """Тестирует обработку ошибки API при получении моделей."""
    mock_groq.return_value.models.list.side_effect = Exception("API Error")
    result = get_available_models("groq", "fake_key")
    assert result == {"error": "API Error"}


# --- НОВЫЕ ТЕСТЫ ДЛЯ ОБРАБОТКИ ОШИБОК JSON И API ---


@patch("app.services.quest_generator.Groq")
def test_create_quest_json_decode_error_raw_content(mock_groq):
    """Тестирует случай, когда LLM возвращает невалидный, но немаркдаун JSON."""
    mock_completion = MagicMock()
    # Simulate invalid JSON without markdown
    mock_completion.choices[0].message.content = "{this is not json}"
    mock_groq.return_value.chat.completions.create.return_value = mock_completion

    with patch("app.services.quest_generator.logger.error") as mock_logger_error:
        result = create_quest_from_setting(
            "любой сеттинг", "fake_key", "groq", "llama3-8b-8192"
        )
        assert "error" in result
        assert "Модель не смогла сгенерировать валидный JSON." in result["error"]
        mock_logger_error.assert_called_once()
        log_message = mock_logger_error.call_args[0][0]
        assert "Raw content (original): '{this is not json}'." in log_message


@patch("app.services.quest_generator.genai")
def test_create_quest_json_decode_error_markdown_valid_json(mock_genai):
    """Тестирует, что очистка markdown работает и валидный JSON внутри парсится."""
    mock_response = MagicMock()
    mock_response.text = '```json\n{"questTitle": "Parsed from markdown"}\n```'
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model

    result = create_quest_from_setting(
        "любой сеттинг", "fake_key", "gemini", "gemini-pro"
    )
    assert result == {"questTitle": "Parsed from markdown"}
    mock_genai.configure.assert_called_once_with(api_key="fake_key")


@patch("app.services.quest_generator.genai")
def test_create_quest_json_decode_error_markdown_invalid_json(mock_genai):
    """Тестирует, что очистка markdown работает, но внутренний JSON невалиден."""
    mock_response_invalid = MagicMock()
    mock_response_invalid.text = (
        '```json\n{"questTitle": "Partial JSON",\n```'  # Invalid JSON
    )
    mock_model_invalid = MagicMock()
    mock_model_invalid.generate_content.return_value = mock_response_invalid
    mock_genai.GenerativeModel.return_value = mock_model_invalid

    with patch("app.services.quest_generator.logger.error") as mock_logger_error:
        result_invalid = create_quest_from_setting(
            "любой сеттинг", "fake_key", "gemini", "gemini-pro"
        )
        assert "error" in result_invalid
        assert (
            "Модель не смогла сгенерировать валидный JSON." in result_invalid["error"]
        )
        mock_logger_error.assert_called_once()
        log_message_invalid = mock_logger_error.call_args[0][0]
        assert (
            'Raw content (original): \'```json\n{"questTitle": "Partial JSON",\n```\'.'
            in log_message_invalid
        )
        assert (
            'Cleaned content: \'{"questTitle": "Partial JSON",\'.'
            in log_message_invalid
        )


@patch("app.services.quest_generator.Groq")
def test_create_quest_api_rate_limit_error(mock_groq):
    """Тестирует обработку ошибки превышения лимита запросов."""
    mock_groq.return_value.chat.completions.create.side_effect = Exception(
        "Too many requests, rate limit exceeded"
    )
    result = create_quest_from_setting(
        "любой сеттинг", "fake_key", "groq", "llama3-8b-8192"
    )
    assert "error" in result
    assert "Превышен лимит запросов к API. Попробуйте позже." in result["error"]


@patch("app.services.quest_generator.Groq")
def test_create_quest_api_invalid_key_error(mock_groq):
    """Тестирует обработку ошибки неверного API ключа."""
    mock_groq.return_value.chat.completions.create.side_effect = Exception(
        "AuthenticationError: Invalid API key"
    )
    result = create_quest_from_setting(
        "любой сеттинг", "fake_key", "groq", "llama3-8b-8192"
    )
    assert "error" in result
    assert "Неверный API ключ. Пожалуйста, проверьте ваш ключ." in result["error"]


@patch("app.services.quest_generator.Groq")
def test_create_quest_api_model_not_found_error(mock_groq):
    """Тестирует обработку ошибки "модель не найдена"."""
    mock_groq.return_value.chat.completions.create.side_effect = Exception(
        "ModelNotFoundError: Model gemma-7b-it not found"
    )
    result = create_quest_from_setting(
        "любой сеттинг", "fake_key", "groq", "gemma-7b-it"
    )
    assert "error" in result
    assert (
        "Выбранная модель 'gemma-7b-it' не найдена, недоступна или устарела у провайдера groq."
        in result["error"]
    )


@patch("app.services.quest_generator.genai")
def test_create_quest_api_model_deprecated_error(mock_genai):
    """Тестирует обработку ошибки "модель устарела"."""
    mock_model_genai = MagicMock()
    mock_model_genai.generate_content.side_effect = Exception(
        "404 Gemini 1.0 Pro Vision has been deprecated on July 12, 2024."
    )
    mock_genai.GenerativeModel.return_value = mock_model_genai
    mock_genai.configure.return_value = None

    result = create_quest_from_setting(
        "любой сеттинг", "fake_key", "gemini", "gemini-1.0-pro-vision"
    )
    assert "error" in result
    assert (
        "Выбранная модель 'gemini-1.0-pro-vision' не найдена, недоступна или устарела у провайдера gemini."
        in result["error"]
    )


@patch("app.services.quest_generator.Groq")
def test_create_quest_api_general_error(mock_groq):
    """Тестирует обработку общей, неопознанной ошибки API."""
    mock_groq.return_value.chat.completions.create.side_effect = Exception(
        "Some unexpected API error occurred."
    )
    result = create_quest_from_setting(
        "любой сеттинг", "fake_key", "groq", "llama3-8b-8192"
    )
    assert "error" in result
    assert (
        "Произошла ошибка при обращении к API groq: Some unexpected API error occurred."
        in result["error"]
    )


@patch("app.services.quest_generator.openai.OpenAI")
def test_create_quest_api_quota_exceeded_error(mock_openai):
    """Тестирует обработку ошибки превышения квоты OpenAI."""
    mock_openai.return_value.chat.completions.create.side_effect = Exception(
        "Error code: 429 - {'error': {'message': 'You exceeded your current quota'}}",
    )
    result = create_quest_from_setting(
        "любой сеттинг", "fake_key", "openai", "gpt-3.5-turbo"
    )
    assert "error" in result
    assert (
        "Превышен лимит использования API или недостаточно средств. Пожалуйста, проверьте ваш тарифный план или баланс."
        in result["error"]
    )


# --- НОВЫЕ ТЕСТЫ ДЛЯ ЛОКАЛЬНОГО ПРОВАЙДЕРА ---


@patch("app.services.quest_generator.os.path.isdir")
@patch("app.services.quest_generator.os.listdir")
def test_get_available_models_local_success(mock_listdir, mock_isdir):
    """Тестирует успешное получение списка локальных GGUF моделей."""
    mock_isdir.return_value = True
    mock_listdir.return_value = ["model1.gguf", "model2.gguf", "readme.txt"]
    with patch("app.services.quest_generator.os.path.isfile", return_value=True):
        result = get_available_models("local", "")
        assert result == {"models": ["model1.gguf", "model2.gguf"]}


@patch("app.services.quest_generator.os.path.isdir")
def test_get_available_models_local_dir_not_found(mock_isdir):
    """Тестирует случай, когда директория с локальными моделями не найдена."""
    mock_isdir.return_value = False
    result = get_available_models("local", "")
    assert result == {"models": []}


def test_validate_api_key_local():
    """Тестирует валидацию для локального провайдера (всегда успешно)."""
    assert validate_api_key("local", "any_key_or_empty") == {"status": "ok"}


@patch("app.services.quest_generator.Llama")
@patch("app.services.quest_generator.os.path.exists")
def test_create_quest_local_success(mock_exists, mock_llama):
    """Тестирует успешную генерацию квеста через локальную модель."""
    mock_exists.return_value = True
    mock_llama_instance = MagicMock()
    mock_llama_instance.create_chat_completion.return_value = {
        "choices": [{"message": {"content": '{"questTitle": "Локальный Квест"}'}}]
    }
    mock_llama.return_value = mock_llama_instance

    result = create_quest_from_setting("любой сеттинг", "", "local", "model1.gguf")

    assert result == {"questTitle": "Локальный Квест"}
    mock_llama.assert_called_once()
    mock_llama_instance.create_chat_completion.assert_called_once()


@patch("app.services.quest_generator.os.path.exists")
def test_create_quest_local_model_not_found(mock_exists, monkeypatch):
    """Тестирует ошибку, если файл локальной модели не найден."""
    # --- ИЗМЕНЕНИЕ: Симулируем, что Llama установлен, чтобы пройти первую проверку ---
    monkeypatch.setattr("app.services.quest_generator.Llama", MagicMock())
    # -----------------------------------------------------------------------
    mock_exists.return_value = False
    result = create_quest_from_setting("любой сеттинг", "", "local", "nonexistent.gguf")
    assert "error" in result
    assert "Локальная модель не найдена" in result["error"]
