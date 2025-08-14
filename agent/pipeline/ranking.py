"""BM25 ranking for candidate papers.

Implements a compact BM25 ranking using only Python standard library to keep
dependencies minimal. Tokenization is a simple lowercased split on non-word
characters, which is sufficient for baseline ranking.
"""

import math
import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

from shared.logging import get_logger

from .models import PaperCandidate

logger = get_logger(__name__)


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    """Tokenize a string into lowercase word characters.

    :param text: Input string.
    :returns: List of tokens.
    """
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]  # naive but fast


def _bm25_scores(
    query_tokens: List[str],
    documents: List[List[str]],
    k1: float = 1.5,
    b: float = 0.75,
) -> List[float]:
    """Compute BM25 scores for pre-tokenized docs.

    Based on standard BM25 with ``idf = ln((N - n + 0.5)/(n + 0.5) + 1)``.

    :param query_tokens: Tokens of the query.
    :param documents: List of token lists for each document.
    :param k1: BM25 parameter (default 1.5).
    :param b: BM25 parameter (default 0.75).
    :returns: A list of scores aligned with ``documents``.
    """

    N = len(documents)
    doc_freq: Dict[str, int] = defaultdict(int)
    for doc_tokens in documents:
        unique_terms = set(doc_tokens)
        for t in unique_terms:
            doc_freq[t] += 1

    avgdl = sum(len(doc) for doc in documents) / max(N, 1)

    idf_cache: Dict[str, float] = {}
    for t in set(query_tokens):
        n = doc_freq.get(t, 0)
        idf_cache[t] = math.log((N - n + 0.5) / (n + 0.5) + 1.0)

    scores: List[float] = []
    for doc_tokens in documents:
        tf = Counter(doc_tokens)
        score = 0.0
        dl = len(doc_tokens)
        for t in query_tokens:
            if t not in tf:
                continue
            idf = idf_cache.get(t, 0.0)
            numerator = tf[t] * (k1 + 1)
            denominator = tf[t] + k1 * (1 - b + b * (dl / max(avgdl, 1e-6)))
            score += idf * (numerator / max(denominator, 1e-6))
        scores.append(score)
    return scores


def rank_candidates(
    *,
    query: str,
    candidates: Iterable[PaperCandidate],
    top_k: int,
) -> List[PaperCandidate]:
    """Rank candidates with BM25 over title + summary and return top-k.

    :param query: Natural-language query.
    :param candidates: Iterable of :class:`PaperCandidate` to be ranked. Candidates
                       are copied to a list internally and scores are written to
                       their ``bm25_score`` attribute.
    :param top_k: Number of items to return after sorting by score and recency.
    :returns: The top-k candidates, sorted by descending score and recency.
    """

    logger.debug(f"Ranking {len(list(candidates))} candidates, top_k={top_k}")
    candidates_list = list(candidates)
    docs_tokens: List[List[str]] = [
        _tokenize(f"{c.title} \n {c.summary}") for c in candidates_list
    ]
    query_tokens = _tokenize(query)
    scores = _bm25_scores(query_tokens, docs_tokens)
    for c, s in zip(candidates_list, scores):
        c.bm25_score = float(s)

    # Stable sort: score desc, recency boost via updated date if present
    def _key(item: PaperCandidate) -> Tuple[float, float]:
        recency = 0.0
        if item.updated:
            recency = item.updated.timestamp()
        return (item.bm25_score, recency)

    candidates_list.sort(key=_key, reverse=True)
    if candidates_list:
        logger.debug(
            f"Top-1 score={candidates_list[0].bm25_score:.3f} id={candidates_list[0].arxiv_id}"
        )
    return candidates_list[:top_k]
