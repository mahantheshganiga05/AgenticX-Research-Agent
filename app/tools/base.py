"""Base schemas and abstractions for agent tools."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Standardized result returned by all tools.
    
    Ensures graceful failure handling without throwing unhandled exceptions.
    """
    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    message: Optional[str] = None
