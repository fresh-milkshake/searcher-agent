"""PubMed manual browsing using NCBI E-utilities (ESearch + ESummary).

No additional dependencies required. Network calls use ``requests`` and return
lightweight ``SearchItem`` objects with stable PubMed IDs.
"""

from typing import Iterator, List, Optional

import requests

from .base import ManualSource, SearchItem


EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedBrowser(ManualSource):
    """Manual source for PubMed articles using E-utilities JSON endpoints."""

    def search(self, query: str, max_results: int = 25, start: int = 0) -> List[SearchItem]:
        """Search PubMed and return a page of results.

        This uses ``esearch.fcgi`` to obtain a list of PMIDs, then ``esummary.fcgi``
        to fetch basic metadata.

        :param query: Free-text query string.
        :param max_results: Maximum number of results to return.
        :param start: Zero-based start index for pagination.
        :returns: List of normalized search items with PMIDs.
        """

        esearch_params = {
            "db": "pubmed",
            "retmode": "json",
            "retmax": str(max_results),
            "retstart": str(start),
            "term": query,
        }
        esearch_resp = requests.get(f"{EUTILS_BASE}/esearch.fcgi", params=esearch_params, timeout=20)
        esearch_resp.raise_for_status()
        esearch_json = esearch_resp.json()
        id_list = esearch_json.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        esummary_params = {
            "db": "pubmed",
            "retmode": "json",
            "id": ",".join(id_list),
        }
        esummary_resp = requests.get(f"{EUTILS_BASE}/esummary.fcgi", params=esummary_params, timeout=20)
        esummary_resp.raise_for_status()
        esummary_json = esummary_resp.json()
        result = esummary_json.get("result", {})

        items: List[SearchItem] = []
        for pmid in id_list:
            info = result.get(pmid, {})
            title = str(info.get("title") or "")
            pubdate = str(info.get("pubdate") or "")
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            snippet = pubdate if pubdate else None
            items.append(SearchItem(title=title, url=url, snippet=snippet, item_id=pmid, extra={"pubdate": pubdate}))
        return items

    def iter_all(self, query: str, chunk_size: int = 100, limit: Optional[int] = None) -> Iterator[SearchItem]:
        """Iterate through PubMed results by fetching in chunks.

        :param query: Free-text query string.
        :param chunk_size: Number of results per request.
        :param limit: Optional maximum number of items to yield.
        :returns: Iterator over normalized search items.
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

    def search_all(self, query: str, chunk_size: int = 100, limit: Optional[int] = None) -> List[SearchItem]:
        """Collect PubMed results for a query into a list.

        :param query: Free-text query string.
        :param chunk_size: Number of results per request.
        :param limit: Optional maximum number of items to collect.
        :returns: List of normalized search items.
        """
        results: List[SearchItem] = []
        for item in self.iter_all(query=query, chunk_size=chunk_size, limit=limit):
            results.append(item)
        return results


