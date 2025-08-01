import pytest
from app.main import app


@pytest.fixture
def client():
    """Создает тестовый клиент Flask для каждого теста."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_route(client):
    """Тестирует, что главная страница загружается успешно."""
    response = client.get("/")
    assert response.status_code == 200
    # Эта строка корректна, так как "QuestGenerator AI" содержит только ASCII
    assert b"QuestGenerator AI" in response.data


def test_settings_route(client):
    """Тестирует, что страница настроек загружается успешно."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert "Настройка".encode("utf-8") in response.data


def test_generate_quest_endpoint_success(client, monkeypatch):
    """
    Тестирует успешный ответ от эндпоинта /generate,
    используя monkeypatch для мока функции.
    """
    mock_quest = {
        "questTitle": "Test Quest",
        "startNodeId": "1",
        "nodes": [],
    }
    monkeypatch.setattr(
        "app.main.create_quest_from_setting",
        lambda setting, api_key, api_provider, model: mock_quest,
    )
    response = client.post(
        "/generate",
        json={
            "setting": "A dark and stormy night",
            "api_key": "test_key",
            "api_provider": "groq",
            "model": "llama3-8b-8192",
        },
    )
    assert response.status_code == 200
    assert response.get_json() == mock_quest


def test_generate_quest_endpoint_missing_data(client):
    """Тестирует ответ 400 при отсутствии данных в запросе."""
    response = client.post("/generate", json={"setting": "A dark and stormy night"})
    assert response.status_code == 400
    assert (
        "Missing 'setting', 'api_key', 'api_provider' or 'model'"
        in response.get_json().get("error", "")
    )


def test_generate_quest_endpoint_generator_error(client, monkeypatch):
    """Тестирует ответ 500, когда генератор квестов возвращает ошибку."""
    error_response = {"error": "Произошла ошибка генерации"}
    monkeypatch.setattr(
        "app.main.create_quest_from_setting",
        lambda setting, api_key, api_provider, model: error_response,
    )
    response = client.post(
        "/generate",
        json={
            "setting": "любой",
            "api_key": "любой",
            "api_provider": "groq",
            "model": "llama3-8b-8192",
        },
    )
    assert response.status_code == 500
    assert response.get_json() == error_response


def test_validate_api_key_endpoint_success(client, monkeypatch):
    """Тестирует успешную валидацию ключа через эндпоинт."""
    monkeypatch.setattr(
        "app.main.validate_api_key", lambda api_provider, api_key: {"status": "ok"}
    )
    response = client.post(
        "/validate_api_key", json={"api_provider": "groq", "api_key": "valid_key"}
    )
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_validate_api_key_endpoint_failure(client, monkeypatch):
    """Тестирует неудачную валидацию ключа через эндпоинт."""
    monkeypatch.setattr(
        "app.main.validate_api_key",
        lambda api_provider, api_key: {
            "status": "error",
            "message": "Неверный API ключ.",
        },
    )
    response = client.post(
        "/validate_api_key", json={"api_provider": "groq", "api_key": "invalid_key"}
    )
    assert response.status_code == 200
    assert response.get_json() == {"status": "error", "message": "Неверный API ключ."}


def test_validate_api_key_endpoint_missing_data(client):
    """Тестирует эндпоинт валидации с отсутствующими данными."""
    response = client.post("/validate_api_key", json={"api_provider": "groq"})
    assert response.status_code == 400
    assert "Missing 'api_key' or 'api_provider'" in response.get_json().get("error", "")


def test_validate_api_key_endpoint_empty_key(client):
    """Тестирует эндпоинт валидации с пустым ключом."""
    response = client.post(
        "/validate_api_key", json={"api_provider": "groq", "api_key": ""}
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "status": "error",
        "message": "API ключ не может быть пустым.",
    }


def test_get_available_models_endpoint_success(client, monkeypatch):
    """Тестирует успешное получение списка моделей."""
    mock_models = {"models": ["model1", "model2"]}
    monkeypatch.setattr(
        "app.main.get_available_models", lambda api_provider, api_key: mock_models
    )
    response = client.post(
        "/api/models", json={"api_provider": "groq", "api_key": "valid_key"}
    )
    assert response.status_code == 200
    assert response.get_json() == mock_models


def test_get_available_models_endpoint_failure(client, monkeypatch):
    """Тестирует неудачное получение списка моделей."""
    error_response = {"error": "Failed to fetch"}
    monkeypatch.setattr(
        "app.main.get_available_models", lambda api_provider, api_key: error_response
    )
    response = client.post(
        "/api/models", json={"api_provider": "groq", "api_key": "invalid_key"}
    )
    assert response.status_code == 200
    assert response.get_json() == error_response


def test_get_available_models_endpoint_missing_data(client):
    """Тестирует эндпоинт получения моделей с отсутствующими данными."""
    response = client.post("/api/models", json={"api_provider": "groq"})
    assert response.status_code == 400
    assert "Missing 'api_key' or 'api_provider'" in response.get_json().get("error", "")
