"""Tests for performance optimization, selective fetch_page, and timing telemetry."""

from unittest.mock import MagicMock, patch
import json
import pytest

from app.agent.research_agent import ResearchAgent
from app.agent.state import AgentState
from app.config import config
from app.tools.base import ToolResult
from app.services.citation_validator import CitationValidator


class TestOptimizationAndSelectiveFetching:
    """Validate that agent optimizes speed without sacrificing correctness or traceability."""

    def test_fetch_page_skipped_when_search_evidence_sufficient(self):
        """When search snippets provide sufficient evidence, agent finishes directly without fetch_page."""
        mock_client = MagicMock()

        # Step 1: web_search -> returns comprehensive snippets
        # Step 2: finish directly because snippets are sufficient
        # Step 3: synthesis call
        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps({
                "thought": "Initiate web search to find applications of generative AI in healthcare.",
                "action": "web_search",
                "query": "generative AI in healthcare applications",
            })),
            MagicMock(text=json.dumps({
                "thought": "Retrieved search snippets already provide rich, comprehensive evidence across clinical notes and radiology. Finishing directly.",
                "action": "finish",
                "reason": "Search snippets contain complete factual evidence.",
            })),
            MagicMock(text=(
                "Generative AI automates clinical documentation [S1] and enhances radiology diagnosis [S2]."
            )),
        ]

        agent = ResearchAgent(gemini_client=mock_client, max_steps=6)

        search_tool_result = ToolResult(
            tool_name="web_search",
            success=True,
            data=[
                {
                    "title": "Clinical GenAI",
                    "url": "https://health.example.com/clinical",
                    "snippet": "Generative AI automates clinical notes and doctor documentation.",
                    "domain": "health.example.com",
                },
                {
                    "title": "Radiology AI",
                    "url": "https://imaging.example.com/radiology",
                    "snippet": "Generative imaging models aid radiologists in detecting anomalies.",
                    "domain": "imaging.example.com",
                },
            ],
        )

        with patch("app.agent.research_agent.web_search", return_value=search_tool_result):
            state = agent.run("What are the main applications of generative AI in healthcare?")

        # Assertions for speed & selective fetching
        assert state.status == "completed"
        assert state.steps_used == 2  # Completed in only 2 steps!
        assert len(state.tool_history) == 2

        tool_names = [h.tool for h in state.tool_history]
        assert "web_search" in tool_names
        assert "finish" in tool_names
        assert "fetch_page" not in tool_names, "fetch_page should be skipped when snippets are sufficient"

        # Traceability assertions
        assert "[S1]" in state.final_answer
        assert "[S2]" in state.final_answer
        assert "### Sources" in state.final_answer

        # Timing assertions
        assert "total_time" in state.timing
        assert "planning_time" in state.timing
        assert "web_search_time" in state.timing
        assert "fetch_page_time" in state.timing
        assert state.timing["fetch_page_time"] == 0.0  # Zero fetch time!
        assert "synthesis_time" in state.timing

    def test_fetch_page_used_when_search_evidence_insufficient(self):
        """When search snippets are shallow or incomplete, agent selects fetch_page for deeper evidence."""
        mock_client = MagicMock()

        mock_client.generate_content.side_effect = [
            # Step 1: web_search
            MagicMock(text=json.dumps({
                "thought": "Search for deep clinical trial results.",
                "action": "web_search",
                "query": "clinical trial deep dive results",
            })),
            # Step 2: fetch_page because snippet was shallow
            MagicMock(text=json.dumps({
                "thought": "Snippet was too shallow to answer full question. Fetching full article text.",
                "action": "fetch_page",
                "url": "https://trials.example.com/study",
            })),
            # Step 3: finish with full evidence
            MagicMock(text=json.dumps({
                "thought": "Full page content retrieved with verified data. Finishing.",
                "action": "finish",
                "reason": "Complete evidence gathered.",
            })),
            # Step 4: synthesis
            MagicMock(text="Clinical trials showed a 34% efficacy improvement with AI synthesis. [S1]"),
        ]

        agent = ResearchAgent(gemini_client=mock_client, max_steps=6)

        search_result = ToolResult(
            tool_name="web_search",
            success=True,
            data=[{
                "title": "Study Overview",
                "url": "https://trials.example.com/study",
                "snippet": "Read more...",  # Shallow snippet
                "domain": "trials.example.com",
            }],
        )

        fetch_result = ToolResult(
            tool_name="fetch_page",
            success=True,
            data={
                "url": "https://trials.example.com/study",
                "title": "Full Clinical Trial Report",
                "content": "Full text: Clinical trials showed a 34% efficacy improvement with AI synthesis.",
                "domain": "trials.example.com",
                "char_count": 80,
            },
        )

        with patch("app.agent.research_agent.web_search", return_value=search_result), \
             patch("app.agent.research_agent.fetch_page", return_value=fetch_result):
            state = agent.run("Detailed study metrics")

        assert state.status == "completed"
        assert state.steps_used == 3
        tool_names = [h.tool for h in state.tool_history]
        assert "web_search" in tool_names
        assert "fetch_page" in tool_names
        assert "finish" in tool_names
        assert "[S1]" in state.final_answer

    def test_citations_work_when_fetch_page_skipped(self):
        """Verify that citations derived purely from web_search snippets validate 100% cleanly."""
        state = AgentState(question="Test question", max_steps=6)
        src1 = state.register_source(
            url="https://example.com/s1",
            title="Search Source 1",
            snippet="Generative AI aids drug discovery.",
            tool="web_search",
            retrieval_status="success",
        )
        src2 = state.register_source(
            url="https://example.com/s2",
            title="Search Source 2",
            snippet="Generative AI drafts medical notes.",
            tool="web_search",
            retrieval_status="success",
        )

        draft = "AI aids drug discovery [S1] and drafts medical documentation [S2]."
        validation = CitationValidator.validate(draft, state.sources)

        assert validation.is_valid is True
        assert validation.cited_ids == ["S1", "S2"]
        assert validation.invalid_ids == []

    def test_six_step_limit_remains_enforced(self):
        """Ensure maximum step limit of 6 is strictly respected."""
        mock_client = MagicMock()
        search_decision = json.dumps({"action": "web_search", "query": "looping query"})
        synthesis = "Loop halted at max limit. [S1]"

        mock_client.generate_content.side_effect = [
            MagicMock(text=search_decision),
            MagicMock(text=search_decision),
            MagicMock(text=search_decision),
            MagicMock(text=search_decision),
            MagicMock(text=search_decision),
            MagicMock(text=search_decision),
            MagicMock(text=synthesis),
        ]

        agent = ResearchAgent(gemini_client=mock_client, max_steps=6)
        search_result = ToolResult(
            tool_name="web_search",
            success=True,
            data=[{"title": "T", "url": "https://ex.com", "snippet": "Data", "domain": "ex.com"}],
        )

        with patch("app.agent.research_agent.web_search", return_value=search_result):
            state = agent.run("Loop test")

        assert state.steps_used == 6
        assert state.status == "step_limit_reached"

    def test_no_unsupported_claims_generated(self):
        """Ensure citation validator rejects answers citing ungrounded phantom IDs (e.g. S99)."""
        state = AgentState(question="Test question", max_steps=6)
        state.register_source(
            url="https://example.com/valid",
            title="Valid",
            snippet="Legitimate information.",
            tool="web_search",
            retrieval_status="success",
        )

        # Draft containing hallucinated S99
        hallucinated_draft = "This fact is substantiated [S1], but this unsupported claim is invented [S99]."
        validation = CitationValidator.validate(hallucinated_draft, state.sources)

        assert validation.is_valid is False
        assert "S99" in validation.invalid_ids
        assert "invalid" in validation.error_message.lower() or "unfetched" in validation.error_message.lower()

    def test_avoid_unnecessary_repeated_searches(self):
        """Ensure the agent avoids executing redundant searches for the identical query string."""
        mock_client = MagicMock()

        # Model requests the identical query twice
        mock_client.generate_content.side_effect = [
            # Step 1: web_search
            MagicMock(text=json.dumps({"action": "web_search", "query": "cancer treatments"})),
            # Step 2: duplicate web_search
            MagicMock(text=json.dumps({"action": "web_search", "query": "cancer treatments"})),
            # Step 3: finish
            MagicMock(text=json.dumps({"action": "finish", "reason": "Done"})),
            # Synthesis
            MagicMock(text="Immunotherapy advances oncology care. [S1]"),
        ]

        agent = ResearchAgent(gemini_client=mock_client, max_steps=6)
        search_result = ToolResult(
            tool_name="web_search",
            success=True,
            data=[{"title": "Oncology", "url": "https://med.com", "snippet": "Immunotherapy advances.", "domain": "med.com"}],
        )

        with patch("app.agent.research_agent.web_search", return_value=search_result) as mock_search:
            state = agent.run("cancer treatments query")

        # web_search should have been called only ONCE by Python!
        assert mock_search.call_count == 1
        # The second search was recorded as skipped duplicate
        assert state.tool_history[1].tool == "web_search"
        assert "Skipped duplicate search" in state.tool_history[1].summary

    def test_timing_information_comprehensive(self):
        """Verify that all 5 timing breakdown fields are present and non-negative."""
        mock_client = MagicMock()
        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps({"action": "finish", "reason": "Sufficient evidence"})),
            MagicMock(text="Answer with evidence. [S1]"),
        ]

        agent = ResearchAgent(gemini_client=mock_client, max_steps=6)
        # Pre-seed source
        state = agent.run("Quick timing test")

        required_keys = ["planning_time", "web_search_time", "fetch_page_time", "synthesis_time", "total_time"]
        for key in required_keys:
            assert key in state.timing
            assert isinstance(state.timing[key], (int, float))
            assert state.timing[key] >= 0.0
