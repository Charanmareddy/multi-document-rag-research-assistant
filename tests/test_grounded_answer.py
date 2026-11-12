"""Context assembly, citation validation, and grounded query orchestration tests."""

import pytest

from backend.app.llm.schemas import CrossDocumentFinding, SynthesisOutput
from backend.app.rag.citation_manager import InvalidCitationError, validate_and_render_citations
from backend.app.rag import query_engine
from backend.app.retrieval.models import Evidence, SearchFilters
from backend.app.retrieval import reranker as reranker_module


class FakeLanguageModel:
    def __init__(self, result: SynthesisOutput) -> None:
        self.result = result
        self.system_instruction = ""
        self.prompt = ""

    def synthesize(self, system_instruction: str, prompt: str) -> SynthesisOutput:
        self.system_instruction = system_instruction
        self.prompt = prompt
        return self.result


def make_evidence() -> Evidence:
    return Evidence(
        chunk_id="chunk-1", document_id="doc-1", document_name="study.pdf",
        collection_id="collection-1", text="The study observed a 20 percent change.",
        page_number=7, section_title="Results", author="Author", score=0.8,
    )


def test_citation_manager_maps_only_retrieved_sources() -> None:
    source = make_evidence()
    output = SynthesisOutput(answer="The study observed a change.", citation_ids=["S1"])

    answer, citations = validate_and_render_citations(output, {"S1": source})

    assert answer.endswith("[S1]")
    assert citations[0]["document_name"] == "study.pdf"
    assert citations[0]["page_number"] == 7


def test_citation_manager_rejects_unknown_labels() -> None:
    output = SynthesisOutput(answer="Finding [S2]", citation_ids=["S2"])
    with pytest.raises(InvalidCitationError, match="unknown source"):
        validate_and_render_citations(output, {"S1": make_evidence()})


def test_query_engine_uses_untrusted_context_and_returns_page_citations(monkeypatch) -> None:
    evidence = make_evidence()
    model = FakeLanguageModel(SynthesisOutput(
        answer="The provided study reports a change.", citation_ids=["S1"],
    ))
    monkeypatch.setattr(query_engine, "bm25_search", lambda *args, **kwargs: [evidence])
    monkeypatch.setattr(query_engine, "get_language_model", lambda: model)

    result = query_engine.answer_question(
        db=None,
        query="What did the study observe?",
        filters=SearchFilters(collection_id="collection-1"),
        mode="bm25",
        rerank=False,
    )

    assert "[S1]" in result["answer"]
    assert result["citations"][0]["page_number"] == 7
    assert "untrusted data" in model.system_instruction
    assert "study.pdf, page 7" in model.prompt
    assert result["timings_ms"]["generation"] >= 0


def test_cross_document_finding_requires_two_distinct_documents() -> None:
    source = make_evidence()
    output = SynthesisOutput(
        answer="The finding is supported.", citation_ids=["S1"],
        agreements=[CrossDocumentFinding(finding="Both documents agree.", source_ids=["S1"])],
    )
    with pytest.raises(InvalidCitationError, match="at least two documents"):
        validate_and_render_citations(output, {"S1": source})


def test_reranker_configuration_failure_falls_back_to_initial_results(monkeypatch) -> None:
    monkeypatch.setattr(reranker_module, "get_settings", lambda: type("Settings", (), {
        "reranker": "cohere", "cohere_api_key": None,
    })())
    evidence = [make_evidence()]

    outcome = reranker_module.rerank_evidence("question", evidence, top_k=1)

    assert outcome.applied is False
    assert outcome.results == evidence
    assert outcome.error and "COHERE_API_KEY" in outcome.error
