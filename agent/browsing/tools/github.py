"""Agent tool for GitHub repository search.

Wraps ``GitHubRepoBrowser`` and returns normalized repository items.
"""

from typing import Dict, List

from agents import function_tool

from agent.browsing.manual.sources.github import GitHubRepoBrowser
from agent.browsing.manual.sources.base import SearchItem


def _item_to_dict(item: SearchItem) -> Dict[str, object]:
    """Convert a repository ``SearchItem`` to a dictionary.

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
def github_repo_search_tool(
    query: str, max_results: int = 10, start: int = 0
) -> List[Dict[str, object]]:
    """Search GitHub repositories via the public Search API.

    :param query: Free-text query string, supports qualifiers (e.g., ``language:Python``).
    :param max_results: Maximum number of results to return.
    :param start: Zero-based start index across results.
    :returns: List of normalized repository dictionaries.
    """
    browser = GitHubRepoBrowser()
    items = browser.search(query=query, max_results=max_results, start=start)
    return [_item_to_dict(it) for it in items]
