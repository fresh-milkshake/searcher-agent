"""Google Scholar manual browsing via DuckDuckGo site-restricted search.

This module intentionally avoids scraping Google Scholar directly. It leverages
the `ddgs` (or legacy ``duckduckgo_search`` as a fallback) package to retrieve
public result snippets limited to the Scholar domain.
"""

from typing import Iterator, List, Optional

# Prefer the new `ddgs` package; fall back to the legacy name to avoid warnings.
try:  # pragma: no cover - import resolution depends on environment
    from ddgs import DDGS  # type: ignore
except Exception:  # pragma: no cover - fallback path in older envs
    from duckduckgo_search import DDGS  # type: ignore

from .base import ManualSource, SearchItem


class GoogleScholarBrowser(ManualSource):
    """Manual source for Google Scholar using site-restricted web search.

    Note: result metadata is limited to title, URL, and snippet.
    """

    def search(
        self, query: str, max_results: int = 25, start: int = 0, *, region: str = "wt-wt"
    ) -> List[SearchItem]:
        """Search Scholar results using DuckDuckGo site restriction.

        :param query: Free-text query string.
        :param max_results: Maximum number of results to return.
        :param start: Zero-based start index; applied client-side.
        :param region: Region code for DuckDuckGo.
        :returns: List of normalized search items.
        """

        # DDG provides a generator that yields up to max_results results.
        # We post-filter for pagination semantics.
        ddg_query = f"site:scholar.google.com {query}".strip()
        items: List[SearchItem] = []
        with DDGS() as ddgs:
            from typing import Any  # local import to avoid global dependency
            # ddgs and duckduckgo_search have different parameter names: query vs keywords
            ddgs_any: Any = ddgs
            text_fn: Any = ddgs_any.text
            try:
                generator = text_fn(query=ddg_query, region=region, max_results=max_results + start)
            except TypeError:
                generator = text_fn(keywords=ddg_query, region=region, max_results=max_results + start)
            for i, res in enumerate(generator):
                if i < start:
                    continue
                title = str(res.get("title") or "")
                url = str(res.get("href") or res.get("link") or res.get("url") or "")
                snippet = str(res.get("body") or res.get("snippet") or res.get("desc") or "")
                if not title and not url:
                    continue
                items.append(SearchItem(title=title, url=url, snippet=snippet, item_id=None, extra=None))
                if len(items) >= max_results:
                    break
        return items

    def iter_all(
        self, query: str, chunk_size: int = 100, limit: Optional[int] = None, *, region: str = "wt-wt"
    ) -> Iterator[SearchItem]:
        """Iterate through Scholar results by fetching in chunks.

        :param query: Free-text query string.
        :param chunk_size: Number of results fetched per request.
        :param limit: Optional maximum number of items to yield.
        :param region: Region code for DuckDuckGo.
        :returns: Iterator over normalized search items.
        """
        yielded = 0
        start = 0
        while True:
            page = self.search(query=query, max_results=chunk_size, start=start, region=region)
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

    def search_all(
        self, query: str, chunk_size: int = 100, limit: Optional[int] = None, *, region: str = "wt-wt"
    ) -> List[SearchItem]:
        """Collect Scholar results for a query into a list.

        :param query: Free-text query string.
        :param chunk_size: Number of results fetched per request.
        :param limit: Optional maximum number of items to collect.
        :param region: Region code for DuckDuckGo.
        :returns: List of normalized search items.
        """
        results: List[SearchItem] = []
        for item in self.iter_all(query=query, chunk_size=chunk_size, limit=limit, region=region):
            results.append(item)
        return results


