"""Search utilities for the pipeline.

This module provides:
- Query generation (simple heuristic without embeddings)
- arXiv retrieval through `shared.arxiv_parser`

All functions are synchronous wrappers around sync parsers to keep things
simple for initial integration. The pipeline orchestrator can run them in
threads or plain sync for now.
"""

from typing import Iterable, List, Optional

from shared.arxiv_parser import ArxivParser
from shared.logger import get_logger

from .models import PaperCandidate, PipelineTask

logger = get_logger(__name__)


def _normalize_query_for_arxiv(query: str) -> str:
    """Normalize boolean query to arXiv syntax and drop unsupported/noisy terms.

    - Remove proximity operators like NEAR/x
    - Remove ultra-generic tokens that harm recall on arXiv (e.g., pdf, document)
    - Collapse whitespace
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
    """Search arXiv and convert results to `PaperCandidate` items.

    Args:
        query: Search query string.
        categories: Optional arXiv categories.
        days_back: Optional days-back time filter.
        max_results: Page size.
        start: Offset for pagination.
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


def collect_candidates(
    task: PipelineTask, queries: Iterable[str], per_query_limit: int = 50
) -> List[PaperCandidate]:
    """Run arXiv search for each query and collect unique candidates by id.

    If no candidates are found with the configured `days_back`, falls back to
    running without a date filter to validate the query set.
    """

    logger = get_logger(__name__)
    seen: set[str] = set()
    collected: List[PaperCandidate] = []
    for q in queries:
        logger.debug(f"Collecting candidates for query: {q}")
        page = arxiv_search(
            query=q,
            categories=task.categories,
            max_results=per_query_limit,
            start=0,
        )
        for c in page:
            if c.arxiv_id in seen:
                continue
            seen.add(c.arxiv_id)
            collected.append(c)
        logger.debug(f"Collected {len(page)} items for query")

    # No date fallbacks anymore

    logger.info(f"Total unique candidates collected: {len(collected)}")
    return collected


def _broaden_query(query: str) -> List[str]:
    """Generate broader variants of a query to improve recall."""
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
