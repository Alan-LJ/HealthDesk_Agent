from fastapi.testclient import TestClient

from app.main import app
from app.schemas.environment import EnvironmentThresholdSettings
from app.storage.repository import HealthRepository


def test_repository_environment_settings_roundtrip(tmp_path):
    repo = HealthRepository(tmp_path / "environment_settings.db")
    settings = EnvironmentThresholdSettings(
        temperature_comfort_min_c=21,
        temperature_comfort_max_c=27,
        humidity_comfort_min_percent=35,
        humidity_comfort_max_percent=58,
        temperature_warning_low_c=18,
        temperature_warning_high_c=30,
        humidity_warning_low_percent=28,
        humidity_warning_high_percent=70,
    )

    saved = repo.save_environment_settings(settings, user_id="sensitive_user")
    loaded = repo.get_environment_settings(user_id="sensitive_user")

    assert loaded.temperature_comfort_min_c == 21
    assert loaded.humidity_comfort_max_percent == 58
    assert loaded.updated_at_ms == saved.updated_at_ms


def test_environment_settings_api_roundtrip():
    client = TestClient(app)
    payload = {
        "temperature_comfort_min_c": 20,
        "temperature_comfort_max_c": 29,
        "humidity_comfort_min_percent": 30,
        "humidity_comfort_max_percent": 62,
        "temperature_warning_low_c": 17,
        "temperature_warning_high_c": 32,
        "humidity_warning_low_percent": 24,
        "humidity_warning_high_percent": 78,
    }

    put_response = client.put("/settings/environment?user_id=api_test_user", json=payload)
    get_response = client.get("/settings/environment?user_id=api_test_user")

    assert put_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json()["temperature_comfort_max_c"] == 29
    assert get_response.json()["humidity_warning_high_percent"] == 78


def test_environment_settings_api_rejects_invalid_ranges():
    client = TestClient(app)
    payload = {
        "temperature_comfort_min_c": 28,
        "temperature_comfort_max_c": 22,
        "humidity_comfort_min_percent": 40,
        "humidity_comfort_max_percent": 60,
        "temperature_warning_low_c": 18,
        "temperature_warning_high_c": 30,
        "humidity_warning_low_percent": 35,
        "humidity_warning_high_percent": 70,
    }

    response = client.put("/settings/environment?user_id=invalid_env_user", json=payload)

    assert response.status_code == 422
