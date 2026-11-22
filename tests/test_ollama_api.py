import httpx
import pytest
from fastapi.testclient import TestClient

from agentmatrix.api import app
from agentmatrix.config import get_settings


@pytest.fixture
def ollama_api(monkeypatch):
    monkeypatch.setenv("AGENTMATRIX_MODE", "ollama")
    monkeypatch.setenv("AGENTMATRIX_OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("AGENTMATRIX_OLLAMA_MODEL", "qwen2.5:7b")
    get_settings.cache_clear()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def test_run_sends_retrieved_evidence_to_ollama(ollama_api, monkeypatch):
    def chat(url, *, json, **kwargs):
        assert url == "http://ollama:11434/api/chat"
        assert json["model"] == "qwen2.5:7b"
        assert json["stream"] is False
        assert "[kb-001] Incident response policy" in json["messages"][1]["content"]
        return httpx.Response(
            200,
            json={"message": {"content": "Production changes require approval [kb-001]."}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", chat)
    response = ollama_api.post("/v1/agent/run", json={"task": "Summarize incident response."})

    assert response.status_code == 200
    assert response.json()["mode"] == "ollama"
    assert response.json()["answer"] == "Production changes require approval [kb-001]."


@pytest.mark.parametrize("model_status,ready_status", [(200, 200), (404, 503)])
def test_readiness_checks_the_configured_model(ollama_api, monkeypatch, model_status, ready_status):
    def show(url, *, json, **kwargs):
        assert url == "http://ollama:11434/api/show"
        assert json == {"model": "qwen2.5:7b"}
        return httpx.Response(model_status, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", show)
    assert ollama_api.get("/ready").status_code == ready_status


@pytest.mark.parametrize(
    "upstream_error,api_status", [(httpx.ConnectError, 502), (httpx.TimeoutException, 504)]
)
def test_run_reports_ollama_failures(ollama_api, monkeypatch, upstream_error, api_status):
    def failed_chat(url, **kwargs):
        raise upstream_error("upstream failure", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", failed_chat)
    response = ollama_api.post("/v1/agent/run", json={"task": "Summarize incident response."})
    assert response.status_code == api_status
