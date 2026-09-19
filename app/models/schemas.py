"""Pydantic schemas for research agent data validation and API exchange."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    """Represents a registered source used during research."""
    source_id: str = Field(description="Deterministic unique ID, e.g. S1, S2")
    title: str = Field(default="Untitled Source", description="Title of the source or webpage")
    url: str = Field(description="URL of the fetched source")
    domain: str = Field(default="", description="Domain name extracted from URL")
    snippet: str = Field(default="", description="Extracted content or snippet")
    tool: str = Field(description="Tool used to retrieve this source ('web_search' or 'fetch_page')")
    retrieval_status: str = Field(default="success", description="Status: 'success', 'failed', or 'empty'")


class ToolCallRecord(BaseModel):
    """Audit record for every tool execution during the agent loop."""
    step: int = Field(description="1-based step index")
    tool: str = Field(description="Name of the tool executed")
    input: dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the tool")
    success: bool = Field(description="Whether the tool succeeded")
    summary: str = Field(default="", description="Human-readable summary of the outcome")


class ClaimCitation(BaseModel):
    """Factual claim mapped to specific source IDs."""
    claim: str
    citations: list[str] = Field(default_factory=list, description="List of source IDs, e.g. ['S1', 'S2']")


class ResearchRequest(BaseModel):
    """API request payload for research questions."""
    question: str = Field(..., min_length=3, description="Research query to answer")
    max_steps: Optional[int] = Field(default=None, description="Optional custom step limit (capped at MAX_AGENT_STEPS)")


class ResearchResponse(BaseModel):
    """Structured response containing verified answer, sources, and audit trace."""
    question: str
    answer: str
    sources: list[SourceItem] = Field(default_factory=list)
    steps_used: int
    max_steps: int
    tool_history: list[ToolCallRecord] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    status: str = Field(description="Final status: 'success', 'step_limit_reached', or 'failed'")
