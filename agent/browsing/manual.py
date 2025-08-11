"""Manual browsing utilities for arXiv.

Provides a simple `ArxivBrowser` class that accepts search queries and returns
results in a convenient, strongly-typed form using the shared arXiv parser.
"""

from datetime import datetime, timedelta
from typing import Iterator, List, Optional

from shared.arxiv_parser import ArxivPaper, ArxivParser


class ArxivBrowser:
    """High-level wrapper for performing arXiv searches.

    The browser exposes simple methods to:
    - Fetch a page of results for a query
    - Iterate over all results for a query in chunks
    - Retrieve a single paper by arXiv ID

    Examples
    --------
    .. code-block:: python

        from agent.browsing.manual import ArxivBrowser

        browser = ArxivBrowser()
        page = browser.search("transformers AND speech", max_results=5)
        print([p.title for p in page])
    """

    def __init__(self, downloads_dir: str = "downloads") -> None:
        """Create a new browser instance.

        Parameters
        ----------
        downloads_dir:
            Directory to use for temporary downloads if needed.
        """
        self._parser = ArxivParser(downloads_dir=downloads_dir)

    def search(
        self,
        query: str,
        max_results: int = 25,
        start: int = 0,
        categories: Optional[List[str]] = None,
        date_from_days: Optional[int] = None,
    ) -> List[ArxivPaper]:
        """Search arXiv and return a single page of results.

        Parameters
        ----------
        query:
            Free-text search query.
        max_results:
            Maximum number of results to return in this page.
        start:
            Pagination start index (0-based) across the full result set.
        categories:
            Optional list of arXiv category filters (e.g., ``["cs.AI"]``).
        date_from_days:
            If provided, limit results to within the last N days.

        Returns
        -------
        list[ArxivPaper]
            A page of results.
        """
        date_from: Optional[datetime] = (
            datetime.now() - timedelta(days=date_from_days)
            if date_from_days is not None
            else None
        )
        return self._parser.search_papers(
            query=query,
            max_results=max_results,
            categories=categories,
            date_from=date_from,
            start=start,
        )

    def iter_all(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        date_from_days: Optional[int] = None,
        chunk_size: int = 100,
        limit: Optional[int] = None,
    ) -> Iterator[ArxivPaper]:
        """Iterate over all results for a query by fetching in chunks.

        Parameters
        ----------
        query:
            Free-text search query.
        categories:
            Optional list of arXiv category filters.
        date_from_days:
            If provided, limit results to within the last N days.
        chunk_size:
            Number of results fetched per request.
        limit:
            If provided, stop after yielding at most ``limit`` results.

        Yields
        ------
        ArxivPaper
            Instances one by one, until exhausted or ``limit`` reached.
        """
        yielded_count = 0
        start = 0
        while True:
            page = self.search(
                query=query,
                max_results=chunk_size,
                start=start,
                categories=categories,
                date_from_days=date_from_days,
            )
            if not page:
                return
            for paper in page:
                if limit is not None and yielded_count >= limit:
                    return
                yielded_count += 1
                yield paper
            start += len(page)
            if len(page) < chunk_size:
                return

    def search_all(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        date_from_days: Optional[int] = None,
        chunk_size: int = 100,
        limit: Optional[int] = None,
    ) -> List[ArxivPaper]:
        """Collect results for a query into a list by consuming the iterator.

        Parameters
        ----------
        query:
            Free-text search query.
        categories:
            Optional list of arXiv category filters.
        date_from_days:
            If provided, limit results to within the last N days.
        chunk_size:
            Number of results fetched per request.
        limit:
            If provided, stop after collecting at most ``limit`` results.

        Returns
        -------
        list[ArxivPaper]
            Collected results list.
        """
        results: List[ArxivPaper] = []
        for paper in self.iter_all(
            query=query,
            categories=categories,
            date_from_days=date_from_days,
            chunk_size=chunk_size,
            limit=limit,
        ):
            results.append(paper)
        return results

    def get(self, arxiv_id: str) -> Optional[ArxivPaper]:
        """Retrieve a single paper by arXiv ID.

        Parameters
        ----------
        arxiv_id:
            The arXiv identifier (with or without version suffix).

        Returns
        -------
        ArxivPaper | None
            The corresponding instance if found; otherwise ``None``.
        """
        return self._parser.get_paper_by_id(arxiv_id)
