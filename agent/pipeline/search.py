"""Search utilities for the pipeline.

This module provides:
- Query generation (simple heuristic without embeddings)
- Retrieval from multiple sources (arXiv, Google Scholar, PubMed, GitHub)

All functions are synchronous wrappers around sync parsers to keep things
simple for initial integration. The pipeline orchestrator can run them in
threads or plain sync for now.
"""

from typing import Iterable, List, Optional

from shared.arxiv_parser import ArxivParser
from shared.logging import get_logger
from agent.browsing.manual.sources.google_scholar import GoogleScholarBrowser
from agent.browsing.manual.sources.pubmed import PubMedBrowser
from agent.browsing.manual.sources.github import GitHubRepoBrowser

from .models import PaperCandidate, PipelineTask, GeneratedQuery

logger = get_logger(__name__)


def _normalize_query_for_arxiv(query: str) -> str:
    """Normalize boolean query to arXiv syntax and drop unsupported/noisy terms.

    - Remove proximity operators like ``NEAR/x``
    - Remove ultra-generic tokens that harm recall on arXiv (e.g., pdf, document)
    - Collapse whitespace

    :param query: Raw query string.
    :returns: Cleaned query string suitable for arXiv search.
    """
    import re

    cleaned = re.sub(r"\bNEAR/\d+\b", " ", query, flags=re.IGNORECASE)
    # Remove mentions of pdf/document which are rarely present in abstracts
    cleaned = re.sub(
        r"\b(pdf|document|doc|pdf2text|pdftables)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Avoid empty parentheses leftovers
    cleaned = re.sub(r"\(\s*\)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def arxiv_search(
    *,
    query: str,
    categories: Optional[List[str]] = None,
    max_results: int = 100,
    start: int = 0,
) -> List[PaperCandidate]:
    """Search arXiv and convert results to :class:`PaperCandidate` items.

    :param query: Search query string.
    :param categories: Optional list of arXiv categories, e.g. ``["cs.AI", "cs.LG"]``.
    :param max_results: Page size for the search request (default 100).
    :param start: Offset for pagination (default 0).
    :returns: A list of candidate papers converted from arXiv results.

    Example::

        items = arxiv_search(query="RAG AND small datasets", max_results=10)
        print(len(items))
    """
    norm_query = _normalize_query_for_arxiv(query)
    logger.debug(
        f"arxiv_search query='{norm_query}' (raw='{query}') categories={categories} start={start} max_results={max_results}"
    )
    parser = ArxivParser()
    papers = parser.search_papers(
        query=norm_query,
        max_results=max_results,
        categories=categories,
        start=start,
    )
    candidates: List[PaperCandidate] = []
    for p in papers:
        candidates.append(
            PaperCandidate(
                arxiv_id=p.id,
                title=p.title,
                summary=p.summary,
                categories=list(p.categories),
                published=p.published,
                updated=p.updated,
                pdf_url=p.pdf_url,
                abs_url=p.abs_url,
                journal_ref=p.journal_ref,
                doi=p.doi,
                comment=p.comment,
                primary_category=p.primary_category,
            )
        )
    logger.info(f"arxiv_search got {len(candidates)} candidates")
    return candidates


def scholar_search(*, query: str, max_results: int = 50, start: int = 0) -> List[PaperCandidate]:
    """Search Google Scholar and convert results to lightweight candidates.

    Since Scholar results do not provide abstracts, the ``summary`` field uses
    the snippet text when available. Categories and arXiv-specific fields are
    left empty.

    :param query: Search query string.
    :param max_results: Page size for the search request (default 50).
    :param start: Offset for pagination (default 0).
    :returns: Candidate list with title and link.
    """
    browser = GoogleScholarBrowser()
    items = browser.search(query=query, max_results=max_results, start=start)
    out: List[PaperCandidate] = []
    for it in items:
        out.append(
            PaperCandidate(
                arxiv_id=it.item_id or it.url,
                title=it.title,
                summary=it.snippet or "",
                categories=[],
                published=None,
                updated=None,
                pdf_url=None,
                abs_url=it.url,
                journal_ref=None,
                doi=None,
                comment=None,
                primary_category=None,
            )
        )
    logger.info(f"scholar_search got {len(out)} candidates")
    return out


def pubmed_search(*, query: str, max_results: int = 50, start: int = 0) -> List[PaperCandidate]:
    """Search PubMed and convert results to candidates.

    :param query: Search query string.
    :param max_results: Page size for the search request (default 50).
    :param start: Offset for pagination (default 0).
    :returns: Candidate list with title and PubMed link.
    """
    browser = PubMedBrowser()
    items = browser.search(query=query, max_results=max_results, start=start)
    out: List[PaperCandidate] = []
    for it in items:
        out.append(
            PaperCandidate(
                arxiv_id=it.item_id or it.url,
                title=it.title,
                summary=it.snippet or "",
                categories=[],
                published=None,
                updated=None,
                pdf_url=None,
                abs_url=it.url,
                journal_ref=None,
                doi=None,
                comment=None,
                primary_category=None,
            )
        )
    logger.info(f"pubmed_search got {len(out)} candidates")
    return out


def github_search(*, query: str, max_results: int = 50, start: int = 0) -> List[PaperCandidate]:
    """Search GitHub repositories and represent them as candidates.

    The pipeline treats repositories as candidates with title and snippet.

    :param query: Search query string.
    :param max_results: Page size for the search request (default 50).
    :param start: Offset for pagination (default 0).
    :returns: Candidate list with repo name and link.
    """
    browser = GitHubRepoBrowser()
    items = browser.search(query=query, max_results=max_results, start=start)
    out: List[PaperCandidate] = []
    for it in items:
        out.append(
            PaperCandidate(
                arxiv_id=it.item_id or it.url,
                title=it.title,
                summary=it.snippet or "",
                categories=[],
                published=None,
                updated=None,
                pdf_url=None,
                abs_url=it.url,
                journal_ref=None,
                doi=None,
                comment=None,
                primary_category=None,
            )
        )
    logger.info(f"github_search got {len(out)} candidates")
    return out


def collect_candidates(
    task: PipelineTask, queries: Iterable[GeneratedQuery], per_query_limit: int = 50
) -> List[PaperCandidate]:
    """Run source-specific search per query and collect unique candidates.

    :param task: The pipeline task providing categories and other context.
    :param queries: Iterable of :class:`GeneratedQuery` with per-query source.
    :param per_query_limit: Max results retrieved for each query (default 50).
    :returns: Unique candidates from all queries.
    """

    logger = get_logger(__name__)
    seen: set[str] = set()
    collected: List[PaperCandidate] = []

    for gq in queries:
        q = gq.query_text
        src = gq.source
        logger.debug(f"Collecting candidates for query: {q} from {src}")

        if src == "arxiv":
            page = arxiv_search(
                query=q, categories=task.categories, max_results=per_query_limit, start=0
            )
        elif src == "scholar":
            page = scholar_search(query=q, max_results=per_query_limit, start=0)
        elif src == "pubmed":
            page = pubmed_search(query=q, max_results=per_query_limit, start=0)
        elif src == "github":
            page = github_search(query=q, max_results=per_query_limit, start=0)
        else:
            logger.warning(f"Unknown source '{src}', skipping query")
            continue

        for c in page:
            if c.arxiv_id in seen:
                continue
            seen.add(c.arxiv_id)
            collected.append(c)
        logger.debug(f"Collected {len(page)} items for query")

    logger.info(f"Total unique candidates collected: {len(collected)}")
    return collected


def _broaden_query(query: str) -> List[str]:
    """Generate broader variants of a query to improve recall.

    :param query: Base query string using ``AND`` between tokens.
    :returns: A small list of broader variants.

    Example::

        _broaden_query("transformers AND medical AND imaging")
        # ['transformers AND medical', 'transformers AND medical', 'transformers medical imaging']
    """
    parts = [p.strip() for p in query.split(" AND ") if p.strip()]
    variants: List[str] = []
    # Drop last clause variant
    if len(parts) > 1:
        variants.append(" AND ".join(parts[:-1]))
    # Keep only first two informative parts
    if len(parts) > 2:
        variants.append(" AND ".join(parts[:2]))
    # Use raw tokens without ANDs
    variants.append(" ".join(parts))
    return variants
