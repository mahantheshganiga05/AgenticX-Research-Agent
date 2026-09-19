"""Tests for citation validation and source traceability."""

import pytest
from app.models.schemas import SourceItem
from app.services.citation_validator import CitationValidator


def create_mock_sources():
    """Helper to create a dictionary of registered sources."""
    return {
        "S1": SourceItem(
            source_id="S1",
            title="GenAI Clinical Documentation",
            url="https://health.example.com/docs",
            domain="health.example.com",
            snippet="Generative AI automates clinical notes and transcripts.",
            tool="web_search",
            retrieval_status="success",
        ),
        "S2": SourceItem(
            source_id="S2",
            title="AI Drug Discovery Insights",
            url="https://pharma.example.com/drugs",
            domain="pharma.example.com",
            snippet="Machine learning accelerates molecular compound screening.",
            tool="fetch_page",
            retrieval_status="success",
        ),
        "S3": SourceItem(
            source_id="S3",
            title="Failed Source",
            url="https://failed.example.com",
            domain="failed.example.com",
            snippet="",
            tool="fetch_page",
            retrieval_status="failed",
        ),
    }


class TestCitationValidator:
    """Tests for CitationValidator logic."""

    def test_extract_citations(self):
        """Test regex extraction of source IDs."""
        text = "Generative AI drafts clinical notes [S1]. It is also used in drug discovery [S2][S3]."
        extracted = CitationValidator.extract_citations(text)
        assert extracted == ["S1", "S2", "S3"]

    def test_valid_citations_accepted(self):
        """Test answer with valid registered citations passes validation."""
        sources = create_mock_sources()
        answer = "AI reduces physician documentation time [S1]. It also assists in molecular screening [S2]."

        result = CitationValidator.validate(answer, sources)
        assert result.is_valid is True
        assert result.cited_ids == ["S1", "S2"]
        assert result.invalid_ids == []
        assert len(result.claims_breakdown) == 2

    def test_missing_citations_rejected(self):
        """Test answer lacking citations is rejected when sources exist."""
        sources = create_mock_sources()
        answer = "AI is used for many things in healthcare including documentation."

        result = CitationValidator.validate(answer, sources)
        assert result.is_valid is False
        assert "contains no citations" in result.error_message

    def test_hallucinated_citations_rejected(self):
        """Test answer citing non-existent source IDs (e.g. [S99]) is rejected."""
        sources = create_mock_sources()
        answer = "AI generates surgical plans [S99] and assists notes [S1]."

        result = CitationValidator.validate(answer, sources)
        assert result.is_valid is False
        assert "S99" in result.invalid_ids
        assert "invalid/unfetched source IDs: S99" in result.error_message

    def test_failed_source_citation_rejected(self):
        """Test answer citing a source whose retrieval failed (S3) is rejected."""
        sources = create_mock_sources()
        answer = "This fact is from a failed page [S3]."

        result = CitationValidator.validate(answer, sources)
        assert result.is_valid is False
        assert "S3" in result.invalid_ids

    def test_sources_section_builder(self):
        """Test formatted sources markdown generation."""
        sources = create_mock_sources()
        section = CitationValidator.build_sources_section(sources, cited_only=True, cited_ids=["S1", "S2"])

        assert "### Sources" in section
        assert "[S1]" in section
        assert "https://health.example.com/docs" in section
        assert "[S2]" in section
        assert "https://pharma.example.com/drugs" in section
        # S3 was not cited, so should not appear
        assert "[S3]" not in section
