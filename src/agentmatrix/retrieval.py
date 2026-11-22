from __future__ import annotations

import re
from dataclasses import dataclass

from agentmatrix.state import Evidence


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str


DEFAULT_KB = [
    Document(
        "kb-001",
        "Incident response policy",
        "Read-only investigation may proceed automatically. Changes to production systems, "
        "credentials, access controls, or external notifications require explicit approval.",
    ),
    Document(
        "kb-002",
        "Agent tool policy",
        "Knowledge search, calculations, and repository reads are read-only. Creating issues, "
        "changing infrastructure, sending messages, or modifying records are write actions.",
    ),
    Document(
        "kb-003",
        "Evidence and provenance standard",
        "Agent answers must include evidence identifiers for material factual claims. Executed "
        "benchmarks must be distinguished from planned or architectural capabilities.",
    ),
]

STOP_WORDS = frozenset(
    "a an and are as at be by can do for from how i in is it of on or should "
    "that the this to was what when where which who will with you".split()
)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS


def retrieve(
    query: str,
    *,
    top_k: int = 3,
    documents: list[Document] | None = None,
) -> list[Evidence]:
    docs = DEFAULT_KB if documents is None else documents
    q = _tokens(query)
    if not q or top_k <= 0:
        return []

    matches: list[tuple[int, Document]] = []
    for doc in docs:
        overlap = len(q & _tokens(f"{doc.title} {doc.text}"))
        if overlap:
            matches.append((overlap, doc))
    if not matches:
        return []

    matches.sort(key=lambda match: (match[0], match[1].id), reverse=True)
    best_overlap = matches[0][0]
    return [
        {
            "id": doc.id,
            "title": doc.title,
            "text": doc.text,
            "score": round(overlap / len(q), 4),
        }
        for overlap, doc in matches[:top_k]
        if 2 * overlap >= best_overlap
    ]
