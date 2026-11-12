"""Structured schema for evidence-grounded synthesis."""

from pydantic import BaseModel, Field


class CrossDocumentFinding(BaseModel):
    """A finding with explicit source labels from retrieved evidence."""

    finding: str = Field(min_length=1, max_length=2000)
    source_ids: list[str] = Field(min_length=1, max_length=10)


class SynthesisOutput(BaseModel):
    """Structured answer returned by configured LLM providers."""

    answer: str = Field(min_length=1, max_length=12000)
    citation_ids: list[str] = Field(min_length=1, max_length=20)
    agreements: list[CrossDocumentFinding] = Field(default_factory=list, max_length=20)
    contradictions: list[CrossDocumentFinding] = Field(default_factory=list, max_length=20)
    caveats: list[str] = Field(default_factory=list, max_length=20)
