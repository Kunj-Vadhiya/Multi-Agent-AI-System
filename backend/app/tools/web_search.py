"""
Modular Web Search Tool for Multi-Agent AI System.

Queries external search APIs to retrieve live web results, structured as:
{
    "query": "...",
    "results": [
        {
            "title": "...",
            "url": "...",
            "snippet": "..."
        }
    ]
}

Supports multiple search providers in a modular fashion:
- DuckDuckGo (zero setup / free out-of-the-box)
- Tavily (via TAVILY_API_KEY)
- Serper / Google (via SERPER_API_KEY)
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SearchProvider(ABC):
    """Abstract base class for modular search providers."""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Execute search and return list of results containing title, url, snippet.
        """
        pass


class DuckDuckGoSearchProvider(SearchProvider):
    """
    Search provider using DuckDuckGo external search.
    Provides free search results without requiring paid API keys.
    """

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        logger.info("Performing web search via DuckDuckGo provider for query: '%s'", query)
        results: List[Dict[str, str]] = []

        try:
            # First try ddgs, then duckduckgo_search
            try:
                from ddgs import DDGS  # type: ignore
            except ImportError:
                from duckduckgo_search import DDGS  # type: ignore

            with DDGS() as ddgs:
                ddgs_gen = ddgs.text(query, max_results=max_results)
                for item in ddgs_gen:
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "url": item.get("href", item.get("link", "")),
                            "snippet": item.get("body", item.get("snippet", "")),
                        }
                    )
        except Exception as err:
            logger.warning("duckduckgo_search library call failed (%s), attempting HTTP fallback", err)
            # HTTP fallback to DuckDuckGo Instant Answer API
            try:
                url = "https://api.duckduckgo.com/"
                params = {"q": query, "format": "json", "no_redirect": "1", "no_html": "1"}
                response = httpx.get(url, params=params, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    abstract = data.get("AbstractText", "")
                    if abstract:
                        results.append(
                            {
                                "title": data.get("Heading", query),
                                "url": data.get("AbstractURL", ""),
                                "snippet": abstract,
                            }
                        )
                    for topic in data.get("RelatedTopics", [])[:max_results]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append(
                                {
                                    "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                                    "url": topic.get("FirstURL", ""),
                                    "snippet": topic.get("Text", ""),
                                }
                            )
            except Exception as http_err:
                logger.error("DuckDuckGo HTTP fallback also failed: %s", http_err)

        return results[:max_results]


class TavilySearchProvider(SearchProvider):
    """
    Search provider using Tavily Search API.
    Requires TAVILY_API_KEY.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, max_results: int = 4) -> List[Dict[str, str]]:
        effective_max = min(max_results, 4)
        logger.info("Performing web search via Tavily API for query: '%s' (max %d)", query, effective_max)
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": effective_max,
            "search_depth": "basic",
        }
        response = httpx.post(url, json=payload, timeout=15.0)
        response.raise_for_status()
        data = response.json()

        results: List[Dict[str, str]] = []
        for item in data.get("results", [])[:effective_max]:
            raw_snippet = item.get("content", item.get("snippet", "")) or ""
            # Truncate snippet to 300 characters to prevent token limit exhaustion
            cleaned_snippet = raw_snippet.strip()[:300]
            results.append(
                {
                    "title": (item.get("title", "") or "")[:120],
                    "url": item.get("url", ""),
                    "snippet": cleaned_snippet,
                }
            )
        return results


class SerperSearchProvider(SearchProvider):
    """
    Search provider using Serper (Google Search) API.
    Requires SERPER_API_KEY.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, max_results: int = 4) -> List[Dict[str, str]]:
        effective_max = min(max_results, 4)
        logger.info("Performing web search via Serper Google API for query: '%s' (max %d)", query, effective_max)
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {"q": query, "num": effective_max}
        response = httpx.post(url, headers=headers, json=payload, timeout=15.0)
        response.raise_for_status()
        data = response.json()

        results: List[Dict[str, str]] = []
        for item in data.get("organic", [])[:effective_max]:
            raw_snippet = item.get("snippet", "") or ""
            results.append(
                {
                    "title": (item.get("title", "") or "")[:120],
                    "url": item.get("link", ""),
                    "snippet": raw_snippet.strip()[:300],
                }
            )
        return results


def get_search_provider() -> SearchProvider:
    """
    Factory function returning the configured SearchProvider instance.
    Checks user setting and available environment API keys.
    """
    provider_name = settings.SEARCH_PROVIDER

    if provider_name == "tavily" or (provider_name == "auto" and settings.TAVILY_API_KEY):
        if settings.TAVILY_API_KEY:
            return TavilySearchProvider(api_key=settings.TAVILY_API_KEY)
        logger.warning("Tavily provider requested but TAVILY_API_KEY is unset; falling back to DuckDuckGo.")

    if provider_name == "serper" or (provider_name == "auto" and settings.SERPER_API_KEY):
        if settings.SERPER_API_KEY:
            return SerperSearchProvider(api_key=settings.SERPER_API_KEY)
        logger.warning("Serper provider requested but SERPER_API_KEY is unset; falling back to DuckDuckGo.")

    return DuckDuckGoSearchProvider()


def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search the web for up-to-date information.

    Args:
        query (str): The search query.
        max_results (int): Maximum number of search results to return (default 5).

    Returns:
        Dict[str, Any]: Structured dictionary with query and results:
            {
                "query": query,
                "results": [
                    {"title": "...", "url": "...", "snippet": "..."}
                ]
            }
    """
    clean_query = query.strip()
    if not clean_query:
        return {"query": query, "results": []}

    try:
        provider = get_search_provider()
        results = provider.search(clean_query, max_results=max_results)
        logger.info("Search for '%s' returned %d results.", clean_query, len(results))
        return {
            "query": clean_query,
            "results": results,
        }
    except Exception as err:
        logger.error("Web search failed for query '%s': %s", clean_query, err)
        return {
            "query": clean_query,
            "results": [],
            "error": f"Search failed: {str(err)}",
        }
