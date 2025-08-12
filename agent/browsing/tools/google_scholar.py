"""Agent tool for Google Scholar search via site-restricted DuckDuckGo.

This wraps ``GoogleScholarBrowser`` and exposes a function tool returning
normalized dictionaries suitable for agent usage.
"""

from typing import Dict, List

from agents import function_tool

from agent.browsing.manual.sources.google_scholar import GoogleScholarBrowser
from agent.browsing.manual.sources.base import SearchItem


def _item_to_dict(item: SearchItem) -> Dict[str, object]:
    """Convert a ``SearchItem`` to a JSON-serializable dictionary.

    :param item: The search item to convert.
    :returns: A dictionary with stable keys.
    """
    return {
        "id": item.item_id,
        "title": item.title,
        "url": item.url,
        "snippet": item.snippet,
        "extra": item.extra or {},
    }


@function_tool
def google_scholar_search_tool(query: str, max_results: int = 10, start: int = 0) -> List[Dict[str, object]]:
    """Search Google Scholar using a site-restricted DuckDuckGo query.

    :param query: Free-text query string.
    :param max_results: Maximum number of results to return.
    :param start: Zero-based start index across results.
    :returns: List of normalized search result dictionaries.
    """
    browser = GoogleScholarBrowser()
    items = browser.search(query=query, max_results=max_results, start=start)
    return [_item_to_dict(it) for it in items]


