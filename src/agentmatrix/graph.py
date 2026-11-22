from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agentmatrix.config import Settings
from agentmatrix.model import deterministic_synthesis, langchain_synthesis, ollama_synthesis
from agentmatrix.policy import contains_injection_pattern
from agentmatrix.retrieval import Document, retrieve
from agentmatrix.state import AgentState


def build_graph(settings: Settings, *, documents: list[Document] | None = None):
    def precheck(state: AgentState) -> dict:
        events = list(state.get("policy_events", []))
        if contains_injection_pattern(state["task"]):
            events.append({"type": "prompt_injection", "action": "blocked"})
            return {
                "policy_events": events,
                "answer": "Request blocked by prompt-injection policy.",
            }
        events.append({"type": "precheck", "action": "pass"})
        return {"policy_events": events}

    def research(state: AgentState) -> dict:
        if state.get("answer"):
            return {}
        return {"evidence": retrieve(state["task"], top_k=3, documents=documents)}

    def synthesize(state: AgentState) -> dict:
        if state.get("answer"):
            return {}
        evidence = state.get("evidence", [])
        if not evidence:
            return {"answer": "I couldn't find relevant evidence in the policy knowledge base."}
        if settings.mode == "langchain":
            answer = langchain_synthesis(state["task"], evidence, settings.model)
        elif settings.mode == "ollama":
            answer = ollama_synthesis(state["task"], evidence, settings)
        else:
            answer = deterministic_synthesis(state["task"], evidence)
        return {"answer": answer}

    graph = StateGraph(AgentState)
    graph.add_node("precheck", precheck)
    graph.add_node("research", research)
    graph.add_node("synthesize", synthesize)
    graph.add_edge(START, "precheck")
    graph.add_edge("precheck", "research")
    graph.add_edge("research", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()
