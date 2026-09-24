"""Agent state management and source registry."""

from typing import Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field

from app.models.schemas import SourceItem, ToolCallRecord, AgentStatus


class AgentState(BaseModel):
    """Encapsulates the full execution state of a research session.
    
    Each research request has its own isolated instance (no global mutable state).
    """
    question: str
    steps_used: int = 0
    max_steps: int = 6
    tool_history: list[ToolCallRecord] = Field(default_factory=list)
    sources: dict[str, SourceItem] = Field(default_factory=dict)
    url_to_source_id: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    final_answer: Optional[str] = None
    status: AgentStatus = AgentStatus.RUNNING

    timing: dict[str, float] = Field(default_factory=lambda: {
        "planning_time": 0.0,
        "web_search_time": 0.0,
        "fetch_page_time": 0.0,
        "synthesis_time": 0.0,
        "total_time": 0.0,
    })
    executed_queries: list[str] = Field(default_factory=list)

    def register_source(
        self,
        url: str,
        title: str,
        snippet: str,
        tool: str,
        retrieval_status: str = "success",
    ) -> SourceItem:
        """Register a new source or update an existing one if the URL was already seen.
        
        Assigns deterministic IDs like S1, S2, S3...
        """
        clean_url = url.strip()
        # Extract domain
        try:
            domain = urlparse(clean_url).netloc or clean_url
        except Exception:
            domain = ""

        # Check if URL already registered
        if clean_url in self.url_to_source_id:
            source_id = self.url_to_source_id[clean_url]
            existing = self.sources[source_id]
            # If deeper content was fetched via fetch_page, enrich existing snippet
            if tool == "fetch_page" and snippet and len(snippet) > len(existing.snippet):
                existing.snippet = snippet
                existing.tool = "fetch_page"
                if title and title != "Untitled Source":
                    existing.title = title
            return existing

        # Assign next sequential ID
        next_index = len(self.sources) + 1
        source_id = f"S{next_index}"

        source_item = SourceItem(
            source_id=source_id,
            title=title or f"Source {next_index}",
            url=clean_url,
            domain=domain,
            snippet=snippet,
            tool=tool,
            retrieval_status=retrieval_status,
        )

        self.sources[source_id] = source_item
        self.url_to_source_id[clean_url] = source_id
        return source_item

    def add_tool_record(
        self,
        tool: str,
        inputs: dict,
        success: bool,
        summary: str,
        duration: Optional[float] = None,
    ) -> ToolCallRecord:
        """Record a completed tool call into the step audit log."""
        record = ToolCallRecord(
            step=self.steps_used,
            tool=tool,
            input=inputs,
            success=success,
            summary=summary,
            duration=round(duration, 2) if duration is not None else None,
        )
        self.tool_history.append(record)
        return record

    def add_error(self, message: str) -> None:
        """Log an error without crashing the agent."""
        self.errors.append(message)

    def get_source_list(self) -> list[SourceItem]:
        """Return list of all registered sources sorted by source_id index."""
        def sort_key(s: SourceItem):
            try:
                return int(s.source_id.replace("S", ""))
            except ValueError:
                return 999
        return sorted(list(self.sources.values()), key=sort_key)
