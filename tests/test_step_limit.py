"""Tests for hard agent step limit enforcement."""

from unittest.mock import MagicMock, patch
import json
import pytest

from app.agent.research_agent import ResearchAgent
from app.agent.state import AgentState
from app.config import config
from app.tools.base import ToolResult


class TestStepLimit:
    """Ensure hard maximum step ceiling cannot be breached under any circumstance."""

    def test_default_max_steps_configuration(self):
        """Verify default configuration enforces MAX_AGENT_STEPS = 6."""
        agent = ResearchAgent(gemini_client=MagicMock())
        assert agent.max_steps == 6
        assert config.MAX_AGENT_STEPS == 6

    def test_agent_never_exceeds_max_steps_when_looping(self):
        """Simulate an LLM that always requests another web_search.
        
        The loop must stop at exactly MAX_AGENT_STEPS = 6 and transition
        to status 'step_limit_reached'.
        """
        mock_client = MagicMock()

        # Decision response always wants another search (infinite loop attempt)
        decision_payload = json.dumps({
            "thought": "I need more information, let me search again.",
            "action": "web_search",
            "query": "healthcare AI endless search",
        })

        # Synthesis response
        synthesis_payload = (
            "Generative AI enhances diagnostics and operational efficiency in healthcare. [S1]"
        )

        mock_client.generate_content.side_effect = [
            # 6 decision calls
            MagicMock(text=decision_payload),
            MagicMock(text=decision_payload),
            MagicMock(text=decision_payload),
            MagicMock(text=decision_payload),
            MagicMock(text=decision_payload),
            MagicMock(text=decision_payload),
            # 1 synthesis call
            MagicMock(text=synthesis_payload),
        ]

        agent = ResearchAgent(gemini_client=mock_client, max_steps=6)

        # Mock web_search tool to succeed and provide evidence
        mock_tool_result = ToolResult(
            tool_name="web_search",
            success=True,
            data=[{
                "title": "Medical AI Overview",
                "url": "https://example.com/ai-med",
                "domain": "example.com",
                "snippet": "AI improves diagnosis accuracy.",
            }],
        )

        with patch("app.agent.research_agent.web_search", return_value=mock_tool_result):
            state = agent.run("What are generative AI applications in healthcare?")

        # Strict checks
        assert state.steps_used == 6, f"Expected 6 steps, but got {state.steps_used}"
        assert state.max_steps == 6
        assert state.status == "step_limit_reached"
        assert len(state.tool_history) == 6
        assert state.final_answer is not None
        assert "Generative AI enhances diagnostics" in state.final_answer

    def test_custom_step_limit_capping(self):
        """Verify custom requested steps cannot exceed the hard ceiling."""
        mock_client = MagicMock()
        mock_client.generate_content.return_value = MagicMock(
            text=json.dumps({"action": "finish", "reason": "done"})
        )

        agent = ResearchAgent(gemini_client=mock_client, max_steps=6)

        # Requesting 20 steps should be clamped to 6
        state = agent.run("Test query", max_steps=20)
        assert state.max_steps == 6

        # Requesting 3 steps (smaller than 6) should be allowed
        state_small = agent.run("Test query", max_steps=3)
        assert state_small.max_steps == 3
