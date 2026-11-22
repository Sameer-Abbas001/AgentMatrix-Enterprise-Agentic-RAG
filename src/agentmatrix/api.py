from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agentmatrix.config import get_settings
from agentmatrix.graph import build_graph
from agentmatrix.model import OllamaError, ollama_model_ready
from agentmatrix.observability import Trace

app = FastAPI(title="AgentMatrix Enterprise", version="0.1.0")
WEB_DIRECTORY = Path(__file__).with_name("web")
app.mount("/assets", StaticFiles(directory=WEB_DIRECTORY / "assets"), name="assets")


class RunRequest(BaseModel):
    task: str = Field(min_length=3, max_length=8000)
    approved: bool = False


@app.get("/", include_in_schema=False)
def workspace() -> FileResponse:
    return FileResponse(WEB_DIRECTORY / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": get_settings().mode}


@app.get("/ready")
def ready() -> dict:
    settings = get_settings()
    if settings.mode != "ollama":
        return {"status": "ready", "mode": settings.mode}
    try:
        ollama_model_ready(settings)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Ollama model is unavailable.") from exc
    return {"status": "ready", "mode": settings.mode, "model": settings.ollama_model}


@app.post("/v1/agent/run")
def run_agent(request: RunRequest) -> dict:
    settings = get_settings()
    trace = Trace()
    graph = build_graph(settings)
    try:
        result = graph.invoke(
            {
                "task": request.task,
                "trace_id": trace.trace_id,
                "evidence": [],
                "tool_calls": [],
                "policy_events": [],
                "requires_approval": False,
                "approved": request.approved,
                "answer": "",
            }
        )
    except httpx.TimeoutException as exc:
        if settings.mode != "ollama":
            raise
        raise HTTPException(status_code=504, detail="Ollama took too long to respond.") from exc
    except (httpx.HTTPError, OllamaError) as exc:
        if settings.mode != "ollama":
            raise
        raise HTTPException(status_code=502, detail="Ollama could not generate an answer.") from exc
    return {
        "trace_id": trace.trace_id,
        "status": "completed",
        "answer": result.get("answer", ""),
        "evidence": result.get("evidence", []),
        "tool_calls": result.get("tool_calls", []),
        "policy_events": result.get("policy_events", []),
        "requires_approval": result.get("requires_approval", False),
        "latency_ms": trace.latency_ms(),
        "mode": settings.mode,
    }
