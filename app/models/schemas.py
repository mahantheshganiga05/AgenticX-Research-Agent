"""Pydantic schemas for research agent data validation and API exchange."""

from typing import Any, Optional
from pydantic import BaseModel, Field
from pydantic_core import core_schema


class AgentStatus(str):
    """Granular execution status supporting backward compatibility."""
    SUCCESS = "success"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    TOOL_FAILURE = "tool_failure"
    LLM_QUOTA_ERROR = "llm_quota_error"
    LLM_ERROR = "llm_error"
    STEP_LIMIT_REACHED = "step_limit_reached"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, str):
            return False
        # Exact match
        if str(self) == other:
            return True
        # Compatibility aliases:
        if str(self) == "success" and other == "completed":
            return True
        if str(self) == "completed" and other == "success":
            return True
        if str(self) in ("tool_failure", "llm_quota_error", "llm_error", "insufficient_evidence", "failed") and other == "failed":
            return True
        return False

    def __hash__(self) -> int:
        return hash(str(self))

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
        )


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
    duration: Optional[float] = Field(default=None, description="Tool execution duration in seconds")


class ClaimCitation(BaseModel):
    """Factual claim mapped to specific source IDs."""
    claim: str
    citations: list[str] = Field(default_factory=list, description="List of source IDs, e.g. ['S1', 'S2']")


class TimingInfo(BaseModel):
    """Granular latency metrics for research workflow."""
    planning_time: float = Field(default=0.0, description="Planning and decision time in seconds")
    web_search_time: float = Field(default=0.0, description="Web search execution time in seconds")
    fetch_page_time: float = Field(default=0.0, description="Web fetch execution time in seconds")
    synthesis_time: float = Field(default=0.0, description="Answer synthesis & validation time in seconds")
    total_time: float = Field(default=0.0, description="Total end-to-end response time in seconds")


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
    status: AgentStatus = Field(description="Final status: 'success', 'insufficient_evidence', 'tool_failure', 'llm_quota_error', 'llm_error', 'step_limit_reached'")
    timing: Optional[TimingInfo] = Field(default=None, description="Latency breakdown metrics")

