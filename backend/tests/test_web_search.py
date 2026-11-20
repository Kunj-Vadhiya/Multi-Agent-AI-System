"""
Unit tests for the modular web search tool.
"""

from typing import Dict, List
from unittest.mock import MagicMock, patch

from app.tools.web_search import DuckDuckGoSearchProvider, SearchProvider, search_web


class DummySearchProvider(SearchProvider):
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        return [
            {
                "title": f"Result for {query}",
                "url": "https://example.com/test",
                "snippet": "Test snippet describing the topic.",
            }
        ]


def test_empty_query():
    res = search_web("")
    assert res["query"] == ""
    assert res["results"] == []


def test_custom_provider_structure():
    with patch("app.tools.web_search.get_search_provider", return_value=DummySearchProvider()):
        res = search_web("RAG architectures", max_results=1)
        assert res["query"] == "RAG architectures"
        assert len(res["results"]) == 1
        item = res["results"][0]
        assert "title" in item
        assert "url" in item
        assert "snippet" in item
        assert item["title"] == "Result for RAG architectures"
        assert item["url"] == "https://example.com/test"


def test_error_handling_graceful():
    mock_provider = MagicMock()
    mock_provider.search.side_effect = RuntimeError("Network timeout")

    with patch("app.tools.web_search.get_search_provider", return_value=mock_provider):
        res = search_web("quantum computing")
        assert res["query"] == "quantum computing"
        assert res["results"] == []
        assert "error" in res
        assert "Network timeout" in res["error"]
