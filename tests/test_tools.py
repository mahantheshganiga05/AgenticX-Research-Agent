"""Tests for research agent tools: web_search and fetch_page."""

from unittest.mock import patch, MagicMock
import httpx
import pytest

from app.tools.web_search import web_search
from app.tools.fetch_page import fetch_page
from app.config import config


class TestWebSearch:
    """Tests for web_search tool."""

    @patch("httpx.Client.post")
    def test_web_search_success(self, mock_post):
        """Test successful search response parsing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Generative AI in Medicine",
                    "url": "https://example.com/healthcare-ai",
                    "content": "AI is used for diagnostic imaging and clinical documentation.",
                }
            ]
        }
        mock_post.return_value = mock_response

        # Temporarily provide dummy key
        with patch.object(config, "TAVILY_API_KEY", "tvly-dummy-key"):
            result = web_search("generative ai healthcare")

        assert result.success is True
        assert result.tool_name == "web_search"
        assert len(result.data) == 1
        assert result.data[0]["title"] == "Generative AI in Medicine"
        assert result.data[0]["url"] == "https://example.com/healthcare-ai"
        assert result.data[0]["domain"] == "example.com"
        assert "diagnostic imaging" in result.data[0]["snippet"]

    @patch("httpx.Client.post")
    def test_web_search_empty_results(self, mock_post):
        """Test search returning zero results handled gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_post.return_value = mock_response

        with patch.object(config, "TAVILY_API_KEY", "tvly-dummy-key"):
            result = web_search("xyznonexistentquery123")

        assert result.success is True
        assert result.data == []
        assert "No results found" in result.message

    def test_web_search_empty_query(self):
        """Test empty query rejection."""
        result = web_search("")
        assert result.success is False
        assert "cannot be empty" in result.error

    def test_web_search_missing_key(self):
        """Test graceful failure when Tavily key is missing."""
        with patch.object(config, "TAVILY_API_KEY", ""):
            result = web_search("test query")
            assert result.success is False
            assert "missing or not configured" in result.error

    @patch("httpx.Client.post")
    def test_web_search_timeout(self, mock_post):
        """Test timeout exception handling."""
        mock_post.side_effect = httpx.TimeoutException("Search timeout")

        with patch.object(config, "TAVILY_API_KEY", "tvly-dummy-key"):
            result = web_search("test query")

        assert result.success is False
        assert "timed out" in result.error.lower()


class TestFetchPage:
    """Tests for fetch_page tool."""

    @patch("httpx.Client.get")
    def test_fetch_page_success(self, mock_get):
        """Test successful web page fetching and HTML cleaning."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = """
        <!DOCTYPE html>
        <html>
        <head><title>AI in Clinical Workflows</title><script>console.log('secret');</script></head>
        <body>
            <nav><a href="/">Home</a></nav>
            <h1>Generative AI Healthcare</h1>
            <p>Generative models reduce physician documentation burden significantly.</p>
            <footer>Copyright 2026</footer>
        </body>
        </html>
        """
        mock_get.return_value = mock_response

        result = fetch_page("https://example.com/ai-article")

        assert result.success is True
        assert result.tool_name == "fetch_page"
        assert result.data["title"] == "AI in Clinical Workflows"
        assert result.data["domain"] == "example.com"
        assert "reduce physician documentation burden" in result.data["content"]
        # Verify script, nav, footer removed
        assert "console.log" not in result.data["content"]
        assert "Copyright" not in result.data["content"]

    @patch("httpx.Client.get")
    def test_fetch_page_404(self, mock_get):
        """Test HTTP 404 response handled gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = fetch_page("https://example.com/not-found")
        assert result.success is False
        assert "HTTP 404" in result.error

    def test_fetch_page_invalid_url(self):
        """Test malformed URL validation."""
        result = fetch_page("not-a-valid-url")
        assert result.success is False
        assert "Invalid URL format" in result.error

    def test_fetch_page_empty_url(self):
        """Test empty URL validation."""
        result = fetch_page("")
        assert result.success is False
        assert "URL cannot be empty" in result.error

    @patch("httpx.Client.get")
    def test_fetch_page_timeout(self, mock_get):
        """Test page request timeout handled gracefully."""
        mock_get.side_effect = httpx.TimeoutException("Read timeout")

        result = fetch_page("https://example.com/slow-page")
        assert result.success is False
        assert "timed out" in result.error.lower()
