"""Tests for graceful tool failure handling and error resiliency."""

from unittest.mock import MagicMock, patch
import json
import pytest

from app.agent.research_agent import ResearchAgent
from app.agent.state import AgentState
from app.config import config
from app.tools.base import ToolResult


class TestGracefulFailures:
    """Ensure agent never crashes upon unexpected tool or network errors."""

    def test_missing_openai_key_returns_graceful_error(self):
        """Test agent behavior when OpenAI API key is completely missing."""
        with patch.object(config, "OPENAI_API_KEY", ""):
            agent = ResearchAgent()
            state = agent.run("What is quantum computing?")

            assert state.status == "failed"
            assert "OpenAI API key is missing" in state.final_answer
            assert len(state.errors) > 0

    def test_all_tools_failing_does_not_invent_answer(self):
        """When web_search returns no evidence, agent must not hallucinate facts."""
        mock_client = MagicMock()

        # Step 1: LLM searches
        # Step 2: LLM finishes because no evidence was found
        mock_client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
                "thought": "Let's search for this obscure query.",
                "action": "web_search",
                "query": "obscure_query_xyz",
            })))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
                "thought": "Search failed, finishing.",
                "action": "finish",
                "reason": "No evidence available.",
            })))]),
        ]

        agent = ResearchAgent(openai_client=mock_client)

        failed_search_result = ToolResult(
            tool_name="web_search",
            success=False,
            data=[],
            error="Connection timed out to search provider.",
        )

        with patch("app.agent.research_agent.web_search", return_value=failed_search_result):
            state = agent.run("Obscure non-existent topic")

        assert state.status == "failed"
        assert "couldn't gather reliable web evidence" in state.final_answer.lower()
        assert len(state.sources) == 0
        assert len(state.errors) >= 1
        assert state.tool_history[0].success is False

    def test_fetch_page_failure_does_not_abort_run(self):
        """When fetch_page fails on a bad URL, the agent records it and continues."""
        mock_client = MagicMock()

        mock_client.chat.completions.create.side_effect = [
            # Step 1: Search
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
                "thought": "Search first",
                "action": "web_search",
                "query": "health AI",
            })))]),
            # Step 2: Fetch broken page
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
                "thought": "Try fetching deep page",
                "action": "fetch_page",
                "url": "https://example.com/broken-link",
            })))]),
            # Step 3: Finish with what we have
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
                "thought": "Finish with search snippet",
                "action": "finish",
                "reason": "Search snippet is enough.",
            })))]),
            # Synthesis
            MagicMock(choices=[MagicMock(message=MagicMock(content="AI is applied in diagnostics. [S1]"))]),
        ]

        agent = ResearchAgent(openai_client=mock_client)

        search_result = ToolResult(
            tool_name="web_search",
            success=True,
            data=[{"title": "Valid Source", "url": "https://example.com/good", "snippet": "AI diagnostics.", "domain": "example.com"}],
        )
        fetch_fail_result = ToolResult(
            tool_name="fetch_page",
            success=False,
            data=None,
            error="HTTP 404: Not Found",
        )

        with patch("app.agent.research_agent.web_search", return_value=search_result), \
             patch("app.agent.research_agent.fetch_page", return_value=fetch_fail_result):
            state = agent.run("health AI question")

        assert state.status == "completed"
        assert state.steps_used == 3
        # Ensure tool history recorded both
        assert state.tool_history[0].tool == "web_search"
        assert state.tool_history[0].success is True
        assert state.tool_history[1].tool == "fetch_page"
        assert state.tool_history[1].success is False
        assert "fetch_page failed" in state.errors[0]
        assert "[S1]" in state.final_answer
