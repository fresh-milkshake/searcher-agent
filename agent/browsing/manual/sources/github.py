"""GitHub manual browsing using the public Search API.

Respects the ``GITHUB_TOKEN`` environment variable if present to increase rate
limits. Returns repository-level results ordered by stars.
"""

import os
from typing import Dict, Iterator, List, Optional, override

import requests

from .base import ManualSource, SearchItem


class GitHubRepoBrowser(ManualSource):
    """Manual source for GitHub repository search."""

    api_url: str = "https://api.github.com/search/repositories"

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": "application/vnd.github+json"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @override
    def search(
        self, query: str, max_results: int = 25, start: int = 0
    ) -> List[SearchItem]:
        """Search repositories by query, sorted by stars in descending order.

        Pagination is mapped from ``start`` and ``max_results`` to GitHub's
        ``page`` and ``per_page`` parameters.

        :param query: Free-text search query, supports qualifiers (e.g., ``language:Python``).
        :param max_results: Maximum number of repositories to return.
        :param start: Zero-based start index across the result stream.
        :returns: List of normalized repository items.
        """

        per_page = max(1, min(100, max_results))
        page = 1 + (start // per_page)
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
            "page": page,
        }

        resp = requests.get(
            self.api_url, params=params, headers=self._headers(), timeout=20
        )
        resp.raise_for_status()
        data = resp.json()
        items_raw = data.get("items", [])

        items: List[SearchItem] = []
        for repo in items_raw:
            full_name = str(repo.get("full_name") or "")
            html_url = str(repo.get("html_url") or "")
            description = repo.get("description")
            stars = repo.get("stargazers_count")
            language = repo.get("language")
            snippet_parts: List[str] = []
            if description:
                snippet_parts.append(str(description))
            if stars is not None:
                snippet_parts.append(f"★ {int(stars)}")
            if language:
                snippet_parts.append(str(language))
            snippet = " • ".join(snippet_parts) if snippet_parts else None
            items.append(
                SearchItem(
                    title=full_name,
                    url=html_url,
                    snippet=snippet,
                    item_id=str(repo.get("id")),
                    extra={"stars": stars, "language": language},
                )
            )

        # Client-side adjust if start not aligned to per_page
        offset = start % per_page
        if offset:
            items = items[offset:]
        return items[:max_results]

    @override
    def iter_all(
        self, query: str, chunk_size: int = 100, limit: Optional[int] = None
    ) -> Iterator[SearchItem]:
        """Iterate through repository search results by fetching in chunks.

        :param query: Free-text search query.
        :param chunk_size: Number of repositories per request.
        :param limit: Optional maximum number of items to yield.
        :returns: Iterator over normalized repository items.
        """
        yielded = 0
        start = 0
        while True:
            page = self.search(query=query, max_results=chunk_size, start=start)
            if not page:
                return
            for item in page:
                if limit is not None and yielded >= limit:
                    return
                yielded += 1
                yield item
            start += len(page)
            if len(page) < chunk_size:
                return

    @override
    def search_all(
        self, query: str, chunk_size: int = 100, limit: Optional[int] = None
    ) -> List[SearchItem]:
        """Collect repository search results for a query into a list.

        :param query: Free-text search query.
        :param chunk_size: Number of repositories per request.
        :param limit: Optional maximum number of items to collect.
        :returns: List of normalized repository items.
        """
        results: List[SearchItem] = []
        for item in self.iter_all(query=query, chunk_size=chunk_size, limit=limit):
            results.append(item)
        return results
