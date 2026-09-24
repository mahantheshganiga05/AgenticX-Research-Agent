"""Tool 1: Web Search Tool.

Searches the web using Tavily API and returns structured results.
Handles missing keys, timeouts, rate limits, and network errors gracefully.
"""

import logging
from typing import Optional
from urllib.parse import urlparse
import httpx

from app.config import config
from app.tools.base import ToolResult

logger = logging.getLogger(__name__)


def web_search(query: str, max_results: Optional[int] = None) -> ToolResult:
    """Search the web for a given query.
    
    Args:
        query: The search query string.
        max_results: Maximum number of search results to return (defaults to config).
        
    Returns:
        ToolResult with data containing a list of dictionaries:
        [{"title": str, "url": str, "snippet": str, "domain": str}]
    """
    tool_name = "web_search"
    clean_query = query.strip() if query else ""
    limit = max_results or config.DEFAULT_SEARCH_MAX_RESULTS

    if not clean_query:
        return ToolResult(
            tool_name=tool_name,
            success=False,
            data=[],
            error="Search query cannot be empty.",
            message="Please provide a valid search query.",
        )

    api_key = config.TAVILY_API_KEY
    if not api_key or api_key == "your_tavily_api_key_here":
        logger.warning("Tavily API key is not configured.")
        return ToolResult(
            tool_name=tool_name,
            success=False,
            data=[],
            error="Tavily API key is missing or not configured. Set TAVILY_API_KEY in .env.",
            message="Search failed due to missing API credentials.",
        )

    # Perform search request
    try:
        # We use httpx directly to have fine-grained control over timeouts, headers, and mockability
        endpoint = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": clean_query,
            "search_depth": "basic",
            "max_results": limit,
            "include_answer": False,
            "include_raw_content": False,
        }

        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            response = client.post(endpoint, json=payload)

        if response.status_code == 401 or response.status_code == 403:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data=[],
                error=f"Authentication failed (HTTP {response.status_code}): Invalid Tavily API key.",
                message="Tavily API authentication failed.",
            )
        elif response.status_code == 429:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data=[],
                error="Tavily rate limit exceeded (HTTP 429). Please try again later.",
                message="Search rate limit reached.",
            )
        elif response.status_code != 200:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data=[],
                error=f"Tavily search API returned HTTP {response.status_code}: {response.text[:200]}",
                message="Search service returned an error.",
            )

        json_data = response.json()
        raw_results = json_data.get("results", [])

        if not raw_results:
            return ToolResult(
                tool_name=tool_name,
                success=True,
                data=[],
                error=None,
                message=f"No results found for query: '{clean_query}'.",
            )

        structured_results = []
        seen_urls = set()
        for item in raw_results:
            url = item.get("url", "").strip()
            if not url:
                continue

            # Deduplicate by normalized URL (lowercase host, path without trailing slash or fragments)
            norm_url = url.split("#")[0].rstrip("/").lower()
            if norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)

            domain = urlparse(url).netloc
            title = item.get("title", "Untitled Source").strip()
            content = item.get("content", "").strip()

            structured_results.append({
                "title": title,
                "url": url,
                "domain": domain,
                "snippet": content,
            })

        # Rank sources to prefer authoritative and rich evidence without discarding non-preferred domains
        ranked_results = rank_and_select_sources(structured_results, clean_query)
        # Cap at requested limit (typically 3-4 sources)
        final_results = ranked_results[:limit]

        return ToolResult(
            tool_name=tool_name,
            success=True,
            data=final_results,
            error=None,
            message=f"Successfully retrieved {len(final_results)} search results for '{clean_query}'.",
        )

    except httpx.TimeoutException:
        logger.error(f"Tavily search timed out for query: '{clean_query}'")
        return ToolResult(
            tool_name=tool_name,
            success=False,
            data=[],
            error=f"Search request timed out after {config.HTTP_TIMEOUT_SECONDS}s.",
            message="Search timed out.",
        )
    except httpx.RequestError as e:
        logger.error(f"Network error during Tavily search: {e}")
        return ToolResult(
            tool_name=tool_name,
            success=False,
            data=[],
            error=f"Network error during search: {str(e)}",
            message="Network error connecting to search service.",
        )
    except Exception as e:
        logger.error(f"Unexpected error in web_search: {e}")
        return ToolResult(
            tool_name=tool_name,
            success=False,
            data=[],
            error=f"Unexpected error: {str(e)}",
            message="An unexpected error occurred during search.",
        )


def rank_and_select_sources(raw_sources: list[dict], query: str) -> list[dict]:
    """Rank search results to prefer authoritative or primary sources where possible.
    
    Adheres to:
    - No hard-coded specific domains (uses general authority signals like .edu, .gov, .org, subdomains).
    - Never removes sources merely because they are not from a preferred domain.
    """
    if not raw_sources:
        return []

    def score_source(item: dict) -> float:
        domain = (item.get("domain") or "").lower()
        snippet = item.get("snippet") or ""
        title = (item.get("title") or "").lower()
        q_tokens = [t for t in query.lower().split() if len(t) > 3]

        score = 0.0

        # General authoritative TLDs / institutional cues (NOT hard-coded domains)
        if any(domain.endswith(tld) for tld in (".edu", ".gov", ".org", ".int", ".mil")):
            score += 2.5
        if any(prefix in domain for prefix in ("research.", "docs.", "arxiv.", "data.", "standards.", "academic.")):
            score += 2.0

        # Informational richness of snippet
        if len(snippet) > 250:
            score += 2.0
        elif len(snippet) > 100:
            score += 1.0

        # Query relevance matching
        token_matches = sum(1 for t in q_tokens if t in title or t in snippet.lower())
        score += min(token_matches * 0.5, 2.0)

        return score

    # Stable sort by authority/relevance score descending
    return sorted(raw_sources, key=score_source, reverse=True)

