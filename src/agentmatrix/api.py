from __future__ import annotations

from asyncio import Semaphore
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agentmatrix.config import get_settings
from agentmatrix.documents import (
    MAX_FILE_BYTES,
    MAX_POLICIES,
    PolicyFileError,
    PolicyText,
    extract_policy,
    policy_passages,
)
from agentmatrix.graph import build_graph
from agentmatrix.model import OllamaError, ollama_model_ready
from agentmatrix.observability import Trace

app = FastAPI(title="AgentMatrix Enterprise", version="0.1.0")
WEB_DIRECTORY = Path(__file__).with_name("web")
app.mount("/assets", StaticFiles(directory=WEB_DIRECTORY / "assets"), name="assets")
policy_parser = Semaphore(1)


class RunRequest(BaseModel):
    task: str = Field(min_length=3, max_length=8000)
    approved: bool = False
    policies: list[PolicyText] = Field(default_factory=list, max_length=MAX_POLICIES)


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


@app.post("/v1/policies/extract")
async def read_policy(
    request: Request,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
) -> PolicyText:
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="Choose a file up to 2 MB.")
        data.extend(chunk)
    async with policy_parser:
        try:
            return await run_in_threadpool(extract_policy, filename, bytes(data))
        except PolicyFileError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/agent/run")
def run_agent(request: RunRequest) -> dict:
    settings = get_settings()
    trace = Trace()
    documents = policy_passages(request.policies) if request.policies else None
    graph = build_graph(settings, documents=documents)
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
