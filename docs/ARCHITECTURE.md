# Architecture Notes

## Control plane

AgentMatrix uses LangGraph as the workflow runtime because enterprise agent systems benefit from explicit state transitions, deterministic control nodes, and auditable boundaries around LLM-driven steps.

## Model plane

The default deterministic synthesizer exists for reproducibility and CI. Ollama generates answers using the retrieved excerpts in the EC2 demo. The LangChain adapter is opt-in.

## Tool plane

The standalone MCP server exposes knowledge search and guarded action proposals. Proposals report the allowlist decision and whether explicit approval is required. The FastAPI Q&A graph runs independently of MCP.

## Evidence plane

The lexical retriever searches the three bundled policies by default. The web workspace
can extract text from uploaded files, keep it in the current browser tab, and send it
with each run. The API splits uploaded text into overlapping passages before retrieval.
Scores measure the share of distinct query terms that match after removing common words.
The graph keeps the strongest matches for synthesis and returns an evidence gap when no
terms match. Hybrid retrieval can be added behind the same `Evidence` contract.

## Evaluation plane

CI runs contract evaluations. Provider-backed releases should add retrieval metrics, trajectory grading, groundedness/faithfulness, safety/adversarial suites, latency, and cost regression thresholds.
