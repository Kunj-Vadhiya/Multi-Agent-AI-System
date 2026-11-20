"""
Image and Visual Media Search Tool for Multi-Agent AI System.

Queries reputable media repositories and platforms (Wikimedia Commons, Wikipedia)
to retrieve relevant images, technical diagrams, architecture charts, illustrations,
and direct source platform links.
"""

import json
import logging
import urllib.parse
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "MultiAgentAIPlatform/1.0 (https://github.com/multi-agent; contact@example.com)"
}


def search_wikimedia_commons(query: str, max_results: int = 4) -> List[Dict[str, Any]]:
    """
    Search Wikimedia Commons for high-quality images, diagrams, and media files.
    """
    results: List[Dict[str, Any]] = []
    try:
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "generator": "search",
            "gsrnamespace": "6",  # File namespace
            "gsrsearch": query,
            "gsrlimit": str(max(max_results * 2, 6)),
            "prop": "imageinfo",
            "iiprop": "url|thumburl|extmetadata",
            "iiurlwidth": "800",
            "format": "json",
        }
        with httpx.Client(timeout=10.0, headers=DEFAULT_HEADERS) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                for page_id, page in pages.items():
                    title = page.get("title", "").replace("File:", "").strip()
                    imageinfo = page.get("imageinfo", [])
                    if not imageinfo:
                        continue
                    info = imageinfo[0]
                    thumb_url = info.get("thumburl") or info.get("url")
                    orig_url = info.get("url")
                    desc_url = f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(page.get('title', ''))}"

                    # Clean up title for caption
                    clean_title = title.rsplit(".", 1)[0].replace("_", " ")
                    ext = title.rsplit(".", 1)[-1].lower() if "." in title else ""

                    # Filter to visual image formats
                    if ext in ("png", "jpg", "jpeg", "svg", "webp", "gif") and thumb_url:
                        results.append(
                            {
                                "title": clean_title,
                                "image_url": thumb_url,
                                "source_url": desc_url,
                                "platform": "Wikimedia Commons",
                                "original_url": orig_url,
                            }
                        )
                        if len(results) >= max_results:
                            break
    except Exception as err:
        logger.warning("[Image Tools] Wikimedia Commons search failed for '%s': %s", query, err)

    return results[:max_results]


def search_wikipedia_images(query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """
    Search English Wikipedia for relevant article lead images, diagrams, and links.
    """
    results: List[Dict[str, Any]] = []
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrlimit": str(max_results * 2),
            "prop": "pageimages|info",
            "inprop": "url",
            "pithumbsize": "800",
            "format": "json",
        }
        with httpx.Client(timeout=10.0, headers=DEFAULT_HEADERS) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                for page_id, page in pages.items():
                    title = page.get("title", "")
                    fullurl = page.get("fullurl") or f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                    thumbnail = page.get("thumbnail", {})
                    thumb_url = thumbnail.get("source")

                    if thumb_url:
                        results.append(
                            {
                                "title": title,
                                "image_url": thumb_url,
                                "source_url": fullurl,
                                "platform": "Wikipedia",
                                "original_url": thumb_url,
                            }
                        )
                        if len(results) >= max_results:
                            break
    except Exception as err:
        logger.warning("[Image Tools] Wikipedia image search failed for '%s': %s", query, err)

    return results[:max_results]


def search_images(query: str, max_results: int = 4) -> Dict[str, Any]:
    """
    Search for relevant images, diagrams, and platform links across Wikimedia Commons and Wikipedia.

    Args:
        query: Subject, concept, technology, or topic to find images and illustrations for.
        max_results: Maximum total images to return.

    Returns:
        Structured dictionary containing a list of image items with title, image_url, source_url, platform.
    """
    clean_query = query.strip()
    logger.info("[Image Tools] Searching images for query: '%s'", clean_query)
    images: List[Dict[str, Any]] = []

    # 1. Search Wikimedia Commons (diagrams, photos, architectures)
    commons_results = search_wikimedia_commons(clean_query, max_results=max_results)
    images.extend(commons_results)

    # 2. Search Wikipedia article images if more needed
    if len(images) < max_results:
        needed = max_results - len(images)
        wiki_results = search_wikipedia_images(clean_query, max_results=needed)
        existing_urls = {img["image_url"] for img in images}
        for item in wiki_results:
            if item["image_url"] not in existing_urls:
                images.append(item)

    selected_images = images[:max_results]

    # Markdown representation helper
    markdown_lines = []
    for item in selected_images:
        markdown_lines.append(f"![{item['title']}]({item['image_url']})")
        markdown_lines.append(f"*Source: [{item['platform']} - {item['title']}]({item['source_url']})*")
        markdown_lines.append("")

    return {
        "query": clean_query,
        "count": len(selected_images),
        "images": selected_images,
        "markdown_preview": "\n".join(markdown_lines),
    }
