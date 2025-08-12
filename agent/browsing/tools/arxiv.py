"""Agent tools for arXiv search and retrieval.

These tools wrap ``shared.arxiv_parser.ArxivParser`` and expose functions
decorated with the OpenAI Agents SDK so they can be invoked by an agent.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from agents import function_tool

from shared.arxiv_parser import ArxivPaper, ArxivParser


def _paper_to_dict(paper: ArxivPaper) -> Dict[str, object]:
    """Convert an :class:`ArxivPaper` dataclass to a JSON-serializable dict.

    :param paper: The :class:`ArxivPaper` instance to convert.
    :returns: Dictionary with stable keys suitable for agent tool responses.
    """
    return {
        "id": paper.id,
        "title": paper.title,
        "authors": list(paper.authors),
        "summary": paper.summary,
        "categories": list(paper.categories),
        "published": paper.published.isoformat() if paper.published else None,
        "updated": paper.updated.isoformat() if paper.updated else None,
        "pdf_url": paper.pdf_url,
        "abs_url": paper.abs_url,
        "journal_ref": paper.journal_ref,
        "doi": paper.doi,
        "comment": paper.comment,
        "primary_category": paper.primary_category,
    }


@function_tool
def arxiv_search_tool(
    query: str,
    max_results: int = 10,
    start: int = 0,
    categories: Optional[List[str]] = None,
    date_from_days: Optional[int] = None,
) -> List[Dict[str, object]]:
    """Search arXiv and return a list of papers.

    :param query: Free-text arXiv search query.
    :param max_results: Maximum number of results to return.
    :param start: Pagination start index (0-based) within the result stream.
    :param categories: Optional list of category filters (e.g., ``["cs.AI", "cs.LG"]``).
    :param date_from_days: If provided, limit results to those submitted within the last N days.
    :returns: List of dictionaries with keys such as ``id``, ``title``, ``authors``,
              ``summary``, ``categories``, ``published``, ``updated``, ``pdf_url``, ``abs_url``.
    """
    parser = ArxivParser()
    date_from: Optional[datetime] = (
        datetime.now() - timedelta(days=date_from_days)
        if date_from_days is not None
        else None
    )
    papers = parser.search_papers(
        query=query,
        max_results=max_results,
        categories=categories,
        date_from=date_from,
        start=start,
    )
    return [_paper_to_dict(p) for p in papers]


@function_tool
def arxiv_get_paper_tool(arxiv_id: str) -> Optional[Dict[str, object]]:
    """Retrieve a single paper by arXiv ID.

    :param arxiv_id: The arXiv identifier (with or without the ``"arXiv:"`` prefix; version suffix allowed).
    :returns: A dictionary representation of the paper if found; otherwise ``None``.
    """
    parser = ArxivParser()
    paper = parser.get_paper_by_id(arxiv_id)
    return _paper_to_dict(paper) if paper is not None else None
