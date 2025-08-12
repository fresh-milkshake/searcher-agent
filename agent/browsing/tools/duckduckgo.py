"""Agent tools for DuckDuckGo web search.

These tools wrap ``duckduckgo_search`` to provide lightweight web search
capabilities for OpenAI agents.
"""

from typing import Dict, List, Optional, Mapping

from agents import function_tool
from duckduckgo_search import DDGS


def _result_to_dict(item: Mapping[str, object]) -> Dict[str, object]:
    """Normalize a DuckDuckGo search item to a stable schema.

    :param item: A dictionary returned by ``duckduckgo_search``.
    :returns: Dictionary containing ``title``, ``href``, ``snippet``, and optional ``extra`` data.
    """
    return {
        "title": item.get("title"),
        "href": item.get("href") or item.get("link") or item.get("url"),
        "snippet": item.get("body") or item.get("snippet") or item.get("desc"),
        "extra": {
            k: v
            for k, v in item.items()
            if k not in {"title", "href", "link", "url", "body", "snippet", "desc"}
        },
    }


@function_tool
def web_search_tool(
    query: str,
    max_results: int = 10,
    region: str = "wt-wt",
    safesearch: str = "moderate",
    timelimit: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Perform a general web search using DuckDuckGo.

    :param query: Free-text search query.
    :param max_results: Maximum number of results to return (1–50 recommended).
    :param region: Region code (e.g., ``"us-en"``, ``"uk-en"``, ``"wt-wt"`` for world-wide).
    :param safesearch: One of ``"off"``, ``"moderate"``, ``"strict"``.
    :param timelimit: Optional time limit (e.g., ``"d"``, ``"w"``, ``"m"``, ``"y"``).
    :returns: List of result dictionaries with ``title``, ``href``, and ``snippet`` keys.
    """
    results: List[Dict[str, object]] = []
    with DDGS() as ddgs:
        for item in ddgs.text(  # type: ignore[call-arg]
            keywords=query,
            region=region,
            safesearch=safesearch,
            timelimit=timelimit,
            max_results=max_results,
        ):
            results.append(_result_to_dict(item))
    return results
