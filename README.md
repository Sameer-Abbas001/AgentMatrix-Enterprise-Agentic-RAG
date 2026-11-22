# AgentMatrix Enterprise

**Evidence-grounded policy Q&A with LangGraph, Ollama, MCP tools, and reproducible evaluation**

> Portfolio project by **Sameer Abbas**.

AgentMatrix Enterprise answers questions over three sample policy documents. It ranks evidence by keyword overlap and sends relevant excerpts to Ollama in the AWS demo. The interviewer workspace shows the answer, retrieved excerpts, match scores, and execution trace. A deterministic mode supports local development and CI without a model API key.

## Project capabilities

- **LangGraph** runs the policy precheck, evidence retrieval, and answer synthesis.
- **Ollama** generates answers on EC2. A separate opt-in **LangChain** adapter supports other providers.
- **Keyword retrieval** ranks the sample policies by the share of meaningful query terms they match. Context includes the highest-ranked sources and any others that match at least half as many terms. Queries with zero matches return an evidence gap before generation.
- **MCP v2** exposes typed knowledge search and action proposal tools over stdio. The proposal tool checks an allowlist and flags write actions for explicit approval.
- **Policy prechecks** detect known prompt-injection phrases.
- **Run traces** include evidence IDs, policy events, and latency. The API response includes a tool-call field for integrations.
- **Offline evaluation** checks expected evidence coverage and the approval response field against tracked fixtures.
- **FastAPI**, **Docker**, and **GitHub Actions** provide the service, packaging, and CI. The repository also includes a static Hugging Face Space bundle.

## Architecture

```text
User / API
   |
   v
Request validation + policy pre-check
   |
   v
Keyword retrieval and ranking
   |
   v
Synthesis with retrieved evidence, or an evidence-gap response
   |
   v
Answer + evidence + run trace
```

The standalone MCP server exposes search and policy proposals to MCP clients. The HTTP Q&A workflow runs independently.

## Safe default mode

`AGENTMATRIX_MODE=deterministic` is the default. It uses the same retrieval and policy precheck, then formats the retrieved evidence into a reproducible answer.

Set `AGENTMATRIX_MODE=langchain` and configure `AGENTMATRIX_MODEL` only when a supported LangChain provider is intentionally available.

Set `AGENTMATRIX_MODE=ollama` to generate answers with a model served by Ollama. For AWS, see the
[deployment guide](deploy/aws/README.md). It runs FastAPI and Ollama together on EC2, with the
API available through AWS Systems Manager Session Manager.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
uvicorn agentmatrix.api:app --reload
```

Open [the research workspace](http://127.0.0.1:8000/) to run a question and review the
answer, evidence, and trace. [Interactive API documentation](http://127.0.0.1:8000/docs)
is also available. To call the API directly:

```bash
curl -X POST http://127.0.0.1:8000/v1/agent/run \
  -H 'Content-Type: application/json' \
  -d '{"task":"Summarize the incident-response policy and identify actions that require approval."}'
```

## MCP server

The project targets the **MCP Python SDK v2** and exposes a minimal typed server:

```bash
python -m agentmatrix.mcp_server
```

The server contains read-only knowledge search and a guarded action proposal tool. Write-like actions return an approval requirement instead of executing side effects.

## Evaluation

```bash
python scripts/evaluate.py
```

The evaluator reads `evals/golden.jsonl` and writes `evaluation.json`. Each deterministic case checks expected evidence ID coverage and the value of the API's approval field. These cases measure the response contract. Ollama answer quality and tool selection require separate evaluation.

Future provider-backed releases can extend this with groundedness, faithfulness, retrieval Recall@K/MRR/NDCG, trajectory grading, and cost regression.

## API response contract

Every run returns a structured envelope:

```json
{
  "trace_id": "...",
  "status": "completed",
  "answer": "...",
  "evidence": [{"id":"kb-001","title":"...","score":0.9}],
  "tool_calls": [],
  "policy_events": [],
  "requires_approval": false,
  "latency_ms": 12.3
}
```

## Repository map

```text
src/agentmatrix/
  api.py            FastAPI service
  config.py         runtime settings
  graph.py          LangGraph orchestration
  model.py          deterministic, Ollama, and LangChain modes
  policy.py         tool/action policy gates
  retrieval.py      evidence retrieval contract
  state.py          graph state types
  mcp_server.py     MCP v2 typed tools
  observability.py  traces and timing
  evaluation.py     offline evaluation primitives

evals/              reproducible benchmark cases
scripts/            evaluation runner
hf_static/          recruiter-facing static Space bundle
tests/              policy/retrieval/API-contract tests
.github/workflows/  CI and security checks
```

## Engineering boundaries

- No fabricated benchmark numbers.
- No autonomous destructive actions.
- No secrets in the repository.
- No claim that external cloud infrastructure is deployed unless execution evidence is committed.
- Tool side effects should be protected by authentication, authorization, audit logging, and explicit approval in a real deployment.

## Current evidence status

| Capability | Status |
|---|---|
| Deterministic agent orchestration | Implemented |
| LangGraph graph | Implemented |
| LangChain provider adapter | Implemented, provider opt-in |
| MCP v2 typed tool server | Implemented |
| Keyword retrieval and Ollama synthesis | Implemented for three sample policies |
| Write-action approval | MCP proposal flag |
| Tool execution and approval resume in web demo | Unimplemented |
| Hybrid retrieval and PII handling | Unimplemented |
| Offline evaluation contract | Implemented |
| FastAPI service | Implemented |
| Docker packaging | Implemented |
| GitHub Actions CI | Implemented |
| Provider-backed LLM benchmark | Not yet claimed |
| Production cloud deployment | Not yet claimed |

## Project management

- **Project charter:** [`PROJECT.md`](PROJECT.md)

## Technology signal

**LangGraph · Ollama · LangChain · MCP · Keyword RAG · FastAPI · Pydantic · Docker · CI · Evaluation · Run traces**

## License

MIT

## Evidence and implementation

Implemented and maintained by **Sameer Abbas** (<sanagsa2028@gmail.com>).

Evidence is deliberately separated into repository-verifiable artifacts and author-confirmed execution. See [EVIDENCE.md](EVIDENCE.md) for the verification matrix, reviewer path and claim boundaries.
