"""Common interfaces and source implementations for manual browsing.

This subpackage defines a small protocol for manual browsing sources and
provides concrete implementations for Google Scholar, PubMed, and GitHub.
"""

from .base import ManualSource, SearchItem
from .google_scholar import GoogleScholarBrowser
from .pubmed import PubMedBrowser
from .github import GitHubRepoBrowser

__all__ = [
    "ManualSource",
    "SearchItem",
    "GoogleScholarBrowser",
    "PubMedBrowser",
    "GitHubRepoBrowser",
]


