"""Integration tests for ResearchAgent workflow and FastAPI endpoints."""

from unittest.mock import MagicMock, patch
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.agent.research_agent import ResearchAgent
from app.tools.base import ToolResult


class TestAgentWorkflow:
    """Verify autonomous tool selection, state progression, and citation integration."""

    def test_multi_tool_selection_and_evidence_integration(self):
        """Verify agent chooses web_search, then fetch_page, then finish.
        
        Satisfies:
        - Criterion 1: Two distinct tools dynamically selected.
        - Criterion 3: Traceable citations attached to fetched source.
        """
        mock_client = MagicMock()

        # 3 decision steps + 1 synthesis step
        mock_client.chat.completions.create.side_effect = [
            # Step 1: choose web_search
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
                "thought": "I need to search for applications of generative AI in healthcare.",
                "action": "web_search",
                "query": "generative AI in healthcare applications",
            })))]),
            # Step 2: choose fetch_page on the discovered URL for deeper evidence
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
                "thought": "The article from HealthTech looks promising. Let's read the full page.",
                "action": "fetch_page",
                "url": "https://healthtech.example.com/genai",
            })))]),
            # Step 3: choose finish
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
                "thought": "I now have sufficient evidence to answer thoroughly.",
                "action": "finish",
                "reason": "Complete evidence gathered.",
            })))]),
            # Step 4: Synthesis call
            MagicMock(choices=[MagicMock(message=MagicMock(content=(
                "Generative AI transforms healthcare by drafting clinical documentation and assisting diagnostics. [S1]"
            )))]),
        ]

        agent = ResearchAgent(openai_client=mock_client, max_steps=6)

        search_tool_result = ToolResult(
            tool_name="web_search",
            success=True,
            data=[{
                "title": "GenAI in Modern Hospitals",
                "url": "https://healthtech.example.com/genai",
                "domain": "healthtech.example.com",
                "snippet": "Initial summary of hospital AI applications.",
            }],
        )

        fetch_tool_result = ToolResult(
            tool_name="fetch_page",
            success=True,
            data={
                "url": "https://healthtech.example.com/genai",
                "title": "GenAI in Modern Hospitals - Deep Dive",
                "content": "Full deep dive text: Doctors save 2 hours daily on notes using generative transcription.",
                "domain": "healthtech.example.com",
                "char_count": 92,
            },
        )

        with patch("app.agent.research_agent.web_search", return_value=search_tool_result), \
             patch("app.agent.research_agent.fetch_page", return_value=fetch_tool_result):
            state = agent.run("What are the main applications of generative AI in healthcare?")

        # Assertions
        assert state.status == "completed"
        assert state.steps_used == 3
        assert len(state.tool_history) == 3

        # Verify BOTH tools were selected
        tool_names = [h.tool for h in state.tool_history]
        assert "web_search" in tool_names
        assert "fetch_page" in tool_names
        assert "finish" in tool_names

        # Verify sources registered
        assert len(state.sources) == 1
        source_item = state.sources["S1"]
        assert source_item.source_id == "S1"
        assert source_item.url == "https://healthtech.example.com/genai"
        assert source_item.tool == "fetch_page"  # Enriched by fetch_page
        assert "Doctors save 2 hours daily" in source_item.snippet

        # Verify final answer and citations
        assert "[S1]" in state.final_answer
        assert "### Sources" in state.final_answer
        assert "https://healthtech.example.com/genai" in state.final_answer


class TestFastAPIRoutes:
    """Test REST API endpoints."""

    def test_health_endpoint(self):
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["max_agent_steps"] == 6

    def test_example_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/example")
        assert response.status_code == 200
        data = response.json()
        assert "examples" in data
        assert len(data["examples"]) >= 3

    def test_root_serves_html(self):
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "Tool-Using Research Agent" in response.text
