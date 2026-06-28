"""Regression tests for the Kagi web-search provider.

PR #e30bd0fc0 migrated Kagi to API v1 and added extract support, but the
extract() method returned a dict error envelope on failure instead of the
list-of-result-dicts shape the web_extract_tool dispatcher expects. This
caused ``'str' object has no attribute 'get'`` when the tool iterated over
the dict keys. These tests lock in the correct return shape.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from plugins.web.kagi.provider import KagiWebSearchProvider


@pytest.fixture
def provider():
    return KagiWebSearchProvider()


class TestKagiExtractErrorShape:
    """extract() must always return a list of result dicts, even on failure."""

    def test_missing_api_key_returns_result_list(self, provider):
        with patch("plugins.web.kagi.provider._load_api_key", return_value=None):
            result = provider.extract(["https://example.com"])

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com"
        assert "KAGI_API_KEY" in result[0]["error"]

    def test_timeout_returns_result_list(self, provider):
        with patch("plugins.web.kagi.provider.requests.post", side_effect=requests.Timeout("boom")):
            result = provider.extract(["https://example.com"])

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com"
        assert "timed out" in result[0]["error"]

    def test_request_exception_returns_result_list(self, provider):
        with patch(
            "plugins.web.kagi.provider.requests.post",
            side_effect=requests.RequestException("network down"),
        ):
            result = provider.extract(["https://example.com"])

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com"
        assert "network down" in result[0]["error"]


class TestKagiExtractSuccess:
    """Normal extract() path parses the API v1 JSON response."""

    def test_extracts_markdown_from_json_response(self, provider):
        fake_resp = requests.Response()
        fake_resp.status_code = 200
        fake_resp._content = b'{"data": [{"url": "https://example.com", "markdown": "# Hello\\n\\nworld"}]}'
        fake_resp.headers["Content-Type"] = "application/json"

        with patch("plugins.web.kagi.provider.requests.post", return_value=fake_resp):
            with patch("plugins.web.kagi.provider._load_api_key", return_value="fake-key"):
                result = provider.extract(["https://example.com"])

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com"
        assert result[0]["title"] == "Hello"
        assert result[0]["content"] == "# Hello\n\nworld"

    def test_extract_markdown_format_single_url_returns_raw_text(self, provider):
        """format='markdown' with a single URL returns raw text, not JSON."""
        fake_resp = requests.Response()
        fake_resp.status_code = 200
        fake_resp._content = b"# Raw Title\n\nRaw body"
        fake_resp.headers["Content-Type"] = "text/markdown"

        with patch("plugins.web.kagi.provider.requests.post", return_value=fake_resp):
            with patch("plugins.web.kagi.provider._load_api_key", return_value="fake-key"):
                result = provider.extract(["https://example.com"], format="markdown")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com"
        assert result[0]["title"] == "Raw Title"
        assert result[0]["content"] == "# Raw Title\n\nRaw body"
