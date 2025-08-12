from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Protocol


@dataclass
class SearchItem:
    """Lightweight search result item for manual browsing.

    :ivar title: Human-readable title of the item.
    :ivar url: Canonical URL for the item.
    :ivar snippet: Optional short snippet or summary.
    :ivar item_id: Optional stable identifier when available, e.g., a PubMed ID.
    :ivar extra: Optional provider-specific metadata.
    """

    title: str
    url: str
    snippet: Optional[str] = None
    item_id: Optional[str] = None
    extra: Optional[dict] = None


class ManualSource(Protocol):
    """Protocol for manual browsing sources.

    Implementations should be stateless or manage their own lightweight state.
    """

    def search(self, query: str, max_results: int = 25, start: int = 0, **kwargs: object) -> List[SearchItem]:
        """Return a single page of results for a query.

        :param query: Free-text query.
        :param max_results: Maximum number of results to return.
        :param start: Zero-based start index for pagination across results.
        :returns: List of search items for the requested page.
        """
        ...

    def iter_all(
        self,
        query: str,
        chunk_size: int = 100,
        limit: Optional[int] = None,
        **kwargs: object,
    ) -> Iterator[SearchItem]:
        """Iterate over results by fetching in chunks.

        :param query: Free-text query.
        :param chunk_size: Number of items to fetch per request.
        :param limit: Optional maximum number of items to yield.
        :returns: Iterator over search items.
        """
        ...

    def search_all(
        self,
        query: str,
        chunk_size: int = 100,
        limit: Optional[int] = None,
        **kwargs: object,
    ) -> List[SearchItem]:
        """Collect results for a query into a list by consuming the iterator.

        :param query: Free-text query.
        :param chunk_size: Number of items to fetch per request.
        :param limit: Optional maximum number of items to collect.
        :returns: List of collected search items.
        """
        ...


def paginate_results(results: Iterable[SearchItem], limit: Optional[int]) -> Iterator[SearchItem]:
    """Yield up to a limit of results from an iterable.

    :param results: Iterable of search items to paginate.
    :param limit: Optional maximum number of items to yield.
    :returns: Iterator yielding up to ``limit`` items.
    """

    count = 0
    for item in results:
        if limit is not None and count >= limit:
            return
        count += 1
        yield item


