"""Manual browsing exports.

This package exposes manual browsing helpers for arXiv and other sources.
"""

from .manual import ArxivBrowser

# Re-export source browsers for convenience
from .sources.google_scholar import GoogleScholarBrowser
from .sources.pubmed import PubMedBrowser
from .sources.github import GitHubRepoBrowser

__all__ = [
    "ArxivBrowser",
    "GoogleScholarBrowser",
    "PubMedBrowser",
    "GitHubRepoBrowser",
]