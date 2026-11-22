---
title: AgentMatrix Enterprise
emoji: 🧠
colorFrom: indigo
colorTo: blue
sdk: static
app_file: index.html
pinned: true
license: mit
short_description: Policy Q&A, evidence retrieval and MCP tools
tags:
- agentic-ai
- langchain
- langgraph
- mcp
- rag
- llm
- mlops
- model-evaluation
- responsible-ai
- ci-cd
---

# AgentMatrix Enterprise

**Evidence-grounded policy Q&A with LangGraph, Ollama, and standalone MCP tools**

This static overview describes the AgentMatrix Enterprise repository. The executable project includes FastAPI, LangGraph, Ollama, an optional LangChain adapter, a standalone MCP v2 server, tests, and Docker packaging.

## Verified engineering evidence

| Check | Executed result |
|---|---|
| Dependency installation | Passed |
| Ruff quality gate | Passed |
| Unit tests | 6/6 passed |
| Deterministic contract evaluation | 3/3 passed |
| Expected evidence recall in contract cases | 1.0 for all 3 cases |
| Expected approval field | Matched in all 3 cases |
| Docker image build | Passed |
| Dependency audit | Passed after audited build-toolchain hardening |

> **Evidence boundary:** the 3/3 result is a deterministic orchestration/evidence-policy contract evaluation, **not** an LLM quality benchmark. Provider-backed LLM accuracy, groundedness, latency, cost and production reliability are not claimed until separately executed and published.

## Architecture

```text
User / API
   ↓
Request validation + policy pre-check
   ↓
Keyword retrieval over three sample policies
   ↓
Answer synthesis with retrieved evidence
   ↓
Answer + evidence + run trace
```

The separate MCP server exposes knowledge search and action proposals. Write proposals return an approval requirement.

## Implemented capabilities

- LangGraph stateful orchestration
- LangChain provider abstraction
- MCP v2 typed tool interoperability
- evidence/provenance contracts
- prompt-injection policy checks
- allowlisted MCP action proposals
- reproducible offline evaluation
- FastAPI service contract
- Docker packaging
- CI/CD and dependency auditing

## Explore

- Project: AgentMatrix Enterprise
- Architecture documentation: `docs/ARCHITECTURE.md`
- Executed baseline evidence: `evaluation/baseline.json`
