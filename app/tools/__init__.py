"""Tools package for Research Agent."""
from app.tools.base import ToolResult
from app.tools.web_search import web_search
from app.tools.fetch_page import fetch_page

__all__ = ["ToolResult", "web_search", "fetch_page"]
