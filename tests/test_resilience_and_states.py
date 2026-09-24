"""Tests for granular agent failure states, quota resilience, and citation traceability.

Covers:
1. Gemini 429 during planning
2. Gemini 429 during synthesis
3. Gemini normal success
4. Search succeeds but synthesis fails
5. Search failure
6. Fetch_page failure
7. Insufficient evidence
8. Step limit
9. Valid citations
10. Invalid citations
11. No fabricated answer after LLM failure
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from google.api_core.exceptions import GoogleAPIError

from app.agent.research_agent import ResearchAgent
from app.agent.state import AgentState
from app.models.schemas import AgentStatus
from app.services.citation_validator import CitationValidator
from app.tools.base import ToolResult


class TestResilienceAndStates:
    """Verify granular failure states and error resilience."""

    def test_gemini_429_during_planning(self):
        """When Gemini returns HTTP 429 during planning, agent must not finish with fallback."""
        mock_client = MagicMock()
        quota_err = GoogleAPIError(
            "429 You exceeded your current quota, please check your plan. "
            "Please retry in 44s."
        )
        mock_client.generate_content.side_effect = quota_err

        agent = ResearchAgent(gemini_client=mock_client)
        state = agent.run("What are the latest developments in fusion energy?")

        assert state.status == "llm_quota_error"
        assert state.status == "failed"
        assert state.status != "success"
        assert state.status != "completed"
        # Must not fabricate an answer
        assert "fusion energy" not in state.final_answer.lower()
        # Must include user-friendly message with retry information
        assert "temporarily unavailable" in state.final_answer.lower()
        assert "quota resets" in state.final_answer.lower()
        assert "44s" in state.final_answer
        # Must record error and not call finish with "Fallback due to planning error."
        assert any("quota" in e.lower() for e in state.errors)
        for h in state.tool_history:
            assert "Fallback due to planning error." not in h.summary

    def test_gemini_429_during_synthesis(self):
        """When search succeeds but synthesis hits Gemini 429, preserve sources and don't fabricate."""
        mock_client = MagicMock()

        # Step 1: Decision to search
        # Step 2: Decision to finish
        # Synthesis: Fails with 429
        quota_err = GoogleAPIError(
            "429 Resource has been exhausted. Please retry in 30s."
        )
        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps({"action": "web_search", "query": "healthcare AI"})),
            MagicMock(text=json.dumps({"action": "finish", "reason": "Sufficient snippets found."})),
            quota_err,
        ]

        agent = ResearchAgent(gemini_client=mock_client)

        search_result = ToolResult(
            tool_name="web_search",
            success=True,
            data=[
                {"title": f"Source {i}", "url": f"https://example.com/{i}", "snippet": f"Snippet {i}", "domain": "example.com"}
                for i in range(1, 5)
            ],
        )

        with patch("app.agent.research_agent.web_search", return_value=search_result):
            state = agent.run("What is AI in healthcare?")

        assert state.status == "llm_quota_error"
        assert state.status == "failed"
        assert state.status != "success"
        # Preserves all collected sources!
        assert len(state.sources) == 4
        # User-friendly message with retry
        assert "temporarily unavailable" in state.final_answer.lower()
        assert "quota resets" in state.final_answer.lower()
        assert "30s" in state.final_answer
        # No fabricated content
        assert "diagnostics" not in state.final_answer.lower()

    def test_gemini_normal_success(self):
        """When Gemini succeeds normally, agent finishes with valid citations and success status."""
        mock_client = MagicMock()
        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps({"action": "web_search", "query": "solar efficiency"})),
            MagicMock(text=json.dumps({"action": "finish", "reason": "Good snippets."})),
            MagicMock(text="Solar cell efficiency has exceeded 26% in silicon photovoltaics. [S1]"),
        ]

        agent = ResearchAgent(gemini_client=mock_client)
        search_result = ToolResult(
            tool_name="web_search",
            success=True,
            data=[{"title": "Solar Research", "url": "https://energy.gov/solar", "snippet": "Solar cell efficiency exceeded 26%.", "domain": "energy.gov"}],
        )

        with patch("app.agent.research_agent.web_search", return_value=search_result):
            state = agent.run("What is current solar efficiency?")

        assert state.status == "success"
        assert state.status == "completed"
        assert "[S1]" in state.final_answer
        assert len(state.sources) == 1

    def test_search_succeeds_but_synthesis_fails(self):
        """When search succeeds but synthesis raises non-429 LLM error, status is llm_error."""
        mock_client = MagicMock()
        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps({"action": "web_search", "query": "quantum computing"})),
            MagicMock(text=json.dumps({"action": "finish", "reason": "Done."})),
            GoogleAPIError("500 Internal error encountered."),
        ]

        agent = ResearchAgent(gemini_client=mock_client)
        search_result = ToolResult(
            tool_name="web_search",
            success=True,
            data=[{"title": "Quantum", "url": "https://example.com/q", "snippet": "Quantum qubits.", "domain": "example.com"}],
        )

        with patch("app.agent.research_agent.web_search", return_value=search_result):
            state = agent.run("How do qubits work?")

        assert state.status == "llm_error"
        assert state.status == "failed"
        assert len(state.sources) == 1
        assert "error occurred while synthesizing" in state.final_answer.lower()

    def test_search_failure(self):
        """When web_search tool fails (network/auth), agent records tool_failure."""
        mock_client = MagicMock()
        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps({"action": "web_search", "query": "dark matter"})),
            MagicMock(text=json.dumps({"action": "finish", "reason": "No results."})),
        ]

        agent = ResearchAgent(gemini_client=mock_client)
        failed_search = ToolResult(
            tool_name="web_search",
            success=False,
            data=[],
            error="Tavily authentication failed (HTTP 401).",
        )

        with patch("app.agent.research_agent.web_search", return_value=failed_search):
            state = agent.run("What is dark matter?")

        assert state.status == "tool_failure"
        assert state.status == "failed"
        assert "tools encountered an error" in state.final_answer.lower()
        assert len(state.sources) == 0

    def test_fetch_page_failure_does_not_prevent_success_with_snippets(self):
        """When fetch_page fails, search snippets are still used for a successful response."""
        mock_client = MagicMock()
        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps({"action": "web_search", "query": "fusion"})),
            MagicMock(text=json.dumps({"action": "fetch_page", "url": "https://example.com/broken"})),
            MagicMock(text=json.dumps({"action": "finish", "reason": "Fallback to search snippet."})),
            MagicMock(text="Fusion produces clean energy from hydrogen isotopes. [S1]"),
        ]

        agent = ResearchAgent(gemini_client=mock_client)
        search_result = ToolResult(
            tool_name="web_search",
            success=True,
            data=[{"title": "Fusion", "url": "https://example.com/broken", "snippet": "Fusion produces clean energy.", "domain": "example.com"}],
        )
        fetch_fail = ToolResult(
            tool_name="fetch_page",
            success=False,
            data=None,
            error="HTTP 404: Not Found",
        )

        with patch("app.agent.research_agent.web_search", return_value=search_result), \
             patch("app.agent.research_agent.fetch_page", return_value=fetch_fail):
            state = agent.run("How does nuclear fusion work?")

        assert state.status == "success"
        assert state.status == "completed"
        assert "[S1]" in state.final_answer
        assert state.tool_history[1].success is False

    def test_insufficient_evidence(self):
        """When search returns empty results without error, status is insufficient_evidence."""
        mock_client = MagicMock()
        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps({"action": "web_search", "query": "xyznonexistent123"})),
            MagicMock(text=json.dumps({"action": "finish", "reason": "No evidence found."})),
        ]

        agent = ResearchAgent(gemini_client=mock_client)
        empty_search = ToolResult(
            tool_name="web_search",
            success=True,
            data=[],
            message="No results found.",
        )

        with patch("app.agent.research_agent.web_search", return_value=empty_search):
            state = agent.run("Find info on xyznonexistent123")

        assert state.status == "insufficient_evidence"
        assert state.status == "failed"
        assert "insufficient evidence" in state.final_answer.lower()
        # Does not fabricate facts
        assert "xyznonexistent123 is a" not in state.final_answer

    def test_step_limit_enforced_at_six(self):
        """Agent must never execute more than MAX_AGENT_STEPS = 6 steps."""
        mock_client = MagicMock()
        # 6 continuous search requests
        decision_search = json.dumps({"action": "web_search", "query": "looping query"})
        mock_client.generate_content.side_effect = [
            MagicMock(text=decision_search),
            MagicMock(text=decision_search),
            MagicMock(text=decision_search),
            MagicMock(text=decision_search),
            MagicMock(text=decision_search),
            MagicMock(text=decision_search),
            # Synthesis
            MagicMock(text="Quantum computing leverages superposition. [S1]"),
        ]

        agent = ResearchAgent(gemini_client=mock_client, max_steps=6)
        search_res = ToolResult(
            tool_name="web_search",
            success=True,
            data=[{"title": "Q", "url": "https://example.com/q", "snippet": "Superposition.", "domain": "example.com"}],
        )

        with patch("app.agent.research_agent.web_search", return_value=search_res):
            state = agent.run("What is quantum computing?")

        assert state.steps_used == 6
        assert state.status == "step_limit_reached"

    def test_valid_citations_enforced(self):
        """Valid citations matching registered sources pass validation."""
        sources = {
            "S1": MagicMock(source_id="S1", retrieval_status="success", url="https://example.com"),
            "S2": MagicMock(source_id="S2", retrieval_status="success", url="https://test.com"),
        }
        answer = "Generative AI improves medical diagnostics [S1] and automates documentation [S2]."
        result = CitationValidator.validate(answer, sources)
        assert result.is_valid is True
        assert "S1" in result.cited_ids
        assert "S2" in result.cited_ids

    def test_invalid_citations_rejected(self):
        """Hallucinated citation IDs like [S99] are detected and rejected."""
        sources = {
            "S1": MagicMock(source_id="S1", retrieval_status="success", url="https://example.com"),
        }
        answer = "Generative AI solves everything [S99]."
        result = CitationValidator.validate(answer, sources)
        assert result.is_valid is False
        assert "S99" in result.invalid_ids

    def test_no_fabricated_answer_after_llm_failure(self):
        """Verify across LLM failures that agent never invents an unverified answer."""
        mock_client = MagicMock()
        mock_client.generate_content.side_effect = GoogleAPIError("429 Quota limit exceeded")

        agent = ResearchAgent(gemini_client=mock_client)
        state = agent.run("What is the cure for cancer?")

        assert state.status == "llm_quota_error"
        # Must not fabricate a cure for cancer!
        assert "cure for cancer" not in state.final_answer.lower()
        assert "temporarily unavailable" in state.final_answer.lower()
