"""Tool 2: Fetch Page Tool.

Fetches web page HTML via HTTP and extracts clean readable text and title.
Handles invalid URLs, 404s, timeouts, and unparseable pages gracefully.
"""

import logging
import re
from typing import Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import httpx

from app.config import config
from app.tools.base import ToolResult

logger = logging.getLogger(__name__)


def fetch_page(url: str) -> ToolResult:
    """Fetch and extract readable content from a specific URL.
    
    Args:
        url: The web page URL to fetch.
        
    Returns:
        ToolResult with data containing:
        {
            "url": str,
            "title": str,
            "content": str,
            "domain": str,
            "char_count": int
        }
    """
    tool_name = "fetch_page"
    clean_url = url.strip() if url else ""

    if not clean_url:
        return ToolResult(
            tool_name=tool_name,
            success=False,
            data=None,
            error="URL cannot be empty.",
            message="Please provide a valid URL.",
        )

    # Basic URL scheme validation
    parsed = urlparse(clean_url)
    if not parsed.scheme or parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ToolResult(
            tool_name=tool_name,
            success=False,
            data=None,
            error=f"Invalid URL format: '{clean_url}'. Must begin with http:// or https://.",
            message="The provided URL is malformed.",
        )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36 AgenticX-ResearchAgent/1.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        with httpx.Client(
            timeout=config.HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            verify=True,
        ) as client:
            response = client.get(clean_url, headers=headers)

        if response.status_code == 404:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data=None,
                error=f"HTTP 404: Page not found at {clean_url}.",
                message="Target webpage does not exist.",
            )
        elif response.status_code == 403:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data=None,
                error=f"HTTP 403: Forbidden access at {clean_url}.",
                message="Target webpage blocked access.",
            )
        elif response.status_code != 200:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data=None,
                error=f"HTTP {response.status_code} error fetching {clean_url}.",
                message="Web server returned an error.",
            )

        content_type = response.headers.get("content-type", "").lower()
        if "text" not in content_type and "html" not in content_type and "json" not in content_type:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data=None,
                error=f"Unsupported content type '{content_type}' at {clean_url}. Expected HTML or text.",
                message="Webpage is not readable text.",
            )

        html_text = response.text
        if not html_text.strip():
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data=None,
                error=f"Empty content returned from {clean_url}.",
                message="Page contains no content.",
            )

        # Parse HTML using BeautifulSoup
        soup = BeautifulSoup(html_text, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        page_title = title_tag.get_text().strip() if title_tag else "Untitled Page"

        # Remove non-content elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "svg"]):
            element.decompose()

        # Extract main text
        raw_text = soup.get_text(separator="\n")

        # Clean whitespace and empty lines
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)

        # Collapse excessive spaces
        cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

        if not cleaned_text.strip():
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data=None,
                error=f"Could not extract meaningful text from {clean_url}.",
                message="Page had no readable body text.",
            )

        # Truncate to maximum characters to keep agent reasoning focused
        max_chars = config.FETCH_PAGE_MAX_CHARS
        truncated_text = cleaned_text[:max_chars]
        if len(cleaned_text) > max_chars:
            truncated_text += f"\n... [Truncated after {max_chars} characters]"

        return ToolResult(
            tool_name=tool_name,
            success=True,
            data={
                "url": clean_url,
                "title": page_title,
                "content": truncated_text,
                "domain": parsed.netloc,
                "char_count": len(truncated_text),
            },
            error=None,
            message=f"Successfully extracted {len(truncated_text)} characters from '{page_title}'.",
        )

    except httpx.TimeoutException:
        logger.error(f"Timeout fetching page {clean_url}")
        return ToolResult(
            tool_name=tool_name,
            success=False,
            data=None,
            error=f"Request to {clean_url} timed out after {config.HTTP_TIMEOUT_SECONDS}s.",
            message="Connection timed out while fetching webpage.",
        )
    except httpx.ConnectError as e:
        logger.error(f"Connection failed for {clean_url}: {e}")
        return ToolResult(
            tool_name=tool_name,
            success=False,
            data=None,
            error=f"Connection failed for {clean_url}: {str(e)}",
            message="Could not connect to host.",
        )
    except Exception as e:
        logger.error(f"Error in fetch_page for {clean_url}: {e}")
        return ToolResult(
            tool_name=tool_name,
            success=False,
            data=None,
            error=f"Unexpected error fetching page: {str(e)}",
            message="An unexpected error occurred while fetching the webpage.",
        )
