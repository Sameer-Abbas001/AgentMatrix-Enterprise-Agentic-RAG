from agentmatrix.retrieval import retrieve


def test_retrieval_returns_evidence_ids():
    results = retrieve("incident response approval", top_k=2)
    assert results
    assert all(item["id"].startswith("kb-") for item in results)
    assert results[0]["score"] >= results[-1]["score"]


def test_retrieval_drops_sources_without_matching_terms():
    results = retrieve("the provenance benchmark standard", top_k=3)

    assert [item["id"] for item in results] == ["kb-003"]
    assert retrieve("what is the capital of France") == []


def test_empty_document_collection_does_not_search_the_default_policies():
    assert retrieve("incident response approval", documents=[]) == []


def test_provenance_question_excludes_weaker_policy_matches():
    results = retrieve(
        "According to the evidence and provenance standard, how should an agent cite "
        "material claims and distinguish benchmark results? Cite the evidence ID in brackets."
    )
    assert [item["id"] for item in results] == ["kb-003"]
