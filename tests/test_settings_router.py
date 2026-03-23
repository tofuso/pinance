"""設定エンドポイントのテスト"""
import pytest
from fastapi.testclient import TestClient
from pinance.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"))
    return TestClient(app)


def test_get_settings_defaults(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm_provider"] == "ollama"
    assert data["llm_model"] == "gemma3:4b-it-qat"
    assert data["llm_base_url"] == "http://localhost:11434"
    assert data["llm_api_key"] == ""


def test_patch_settings(client):
    resp = client.patch("/api/settings", json={"llm_model": "mistral"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm_model"] == "mistral"
    # 他のフィールドは変わらない
    assert data["llm_provider"] == "ollama"


def test_patch_settings_multiple_fields(client):
    resp = client.patch("/api/settings", json={
        "llm_provider": "claude",
        "llm_model": "claude-sonnet-4-6",
        "llm_api_key": "sk-test",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm_provider"] == "claude"
    assert data["llm_model"] == "claude-sonnet-4-6"
    assert data["llm_api_key"] == "sk-test"
