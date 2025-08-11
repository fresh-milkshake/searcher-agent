"""arXiv client with convenient typed wrappers.

This module provides :class:`ArxivParser` and helper functions to search for
papers, fetch metadata, download PDFs, and extract text. It is intentionally
lightweight and dependency-minimal.

Examples
--------
.. code-block:: python

    from shared.arxiv_parser import ArxivParser

    parser = ArxivParser()
    results = parser.search_papers("RAG small datasets", max_results=5)
    for p in results:
        print(p.id, p.title)
"""

import os
import re
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path

import arxiv
import requests
from bs4 import BeautifulSoup
import PyPDF2

logger = logging.getLogger(__name__)


@dataclass
class ArxivPaper:
    """Class for representing a scientific article from arXiv"""

    id: str
    title: str
    authors: List[str]
    summary: str
    categories: List[str]
    published: datetime
    updated: datetime
    pdf_url: str
    abs_url: str
    journal_ref: Optional[str] = None
    doi: Optional[str] = None
    comment: Optional[str] = None
    primary_category: Optional[str] = None


class ArxivParser:
    """Main class for working with the arXiv API.

    Parameters
    ----------
    downloads_dir:
        Directory used to store temporary files when downloading PDFs.
    """

    def __init__(self, downloads_dir: str = "downloads"):
        """
        Initialize parser

        Args:
            downloads_dir: Directory for saving downloaded files
        """
        self.client = arxiv.Client()
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(exist_ok=True)

    def search_papers(
        self,
        query: str,
        max_results: int = 10,
        sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance,
        sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending,
        categories: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        start: int = 0,
    ) -> List[ArxivPaper]:
        """Search articles by query with optional filters.

        Parameters
        ----------
        query:
            Search query string.
        max_results:
            Maximum number of results to return.
        sort_by:
            Sort criterion, e.g., ``arxiv.SortCriterion.Relevance``.
        sort_order:
            Sort order, e.g., ``arxiv.SortOrder.Descending``.
        categories:
            Category filter like ``["cs.AI", "cs.LG"]``.
        date_from:
            Start date for results (inclusive).
        date_to:
            End date for results (inclusive).
        start:
            Starting index for pagination (default 0).

        Returns
        -------
        list[ArxivPaper]
            Found papers as typed records.
        """
        try:
            # Build search query
            search_query = self._build_search_query(
                query, categories, date_from, date_to
            )

            # Create search object
            search = arxiv.Search(
                query=search_query,
                max_results=max_results,
                sort_by=sort_by,
                sort_order=sort_order,
            )

            # Execute search with pagination support
            results = []
            processed_count = 0
            skipped_count = 0

            for result in self.client.results(search):
                # Skip results until we reach the start position
                if skipped_count < start:
                    skipped_count += 1
                    continue

                # Stop when we have enough results
                if processed_count >= max_results:
                    break

                paper = self._convert_to_arxiv_paper(result)
                results.append(paper)
                processed_count += 1

            logger.info(
                f"Found {len(results)} articles for query: {query} (start={start}, skipped={skipped_count})"
            )
            return results

        except Exception as e:
            logger.error(f"Error searching articles: {e}")
            return []

    def get_paper_by_id(self, arxiv_id: str) -> Optional[ArxivPaper]:
        """Get article data by ID.

        Parameters
        ----------
        arxiv_id:
            Article ID on arXiv (e.g., ``"2301.07041"``)

        Returns
        -------
        ArxivPaper | None
            The paper if found, otherwise ``None``.
        """
        try:
            # Normalize ID
            clean_id = self._clean_arxiv_id(arxiv_id)

            # Create search query by ID
            search = arxiv.Search(id_list=[clean_id])

            # Get result
            results = list(self.client.results(search))
            if results:
                paper = self._convert_to_arxiv_paper(results[0])
                logger.info(f"Found article: {paper.title}")
                return paper
            else:
                logger.warning(f"Article with ID {arxiv_id} not found")
                return None

        except Exception as e:
            logger.error(f"Error getting article {arxiv_id}: {e}")
            return None

    def download_pdf(
        self, paper: ArxivPaper, filename: Optional[str] = None
    ) -> Optional[str]:
        """Download a paper's PDF file.

        Parameters
        ----------
        paper:
            The paper to download.
        filename:
            Optional filename override; defaults to a safe name from id/title.

        Returns
        -------
        str | None
            Path to the downloaded file or ``None`` on error.
        """
        try:
            if not filename:
                # Generate filename from ID and title
                safe_title = re.sub(r"[^\w\s-]", "", paper.title)[:50]
                safe_title = re.sub(r"[-\s]+", "-", safe_title)
                filename = f"{paper.id}_{safe_title}.pdf"

            filepath = self.downloads_dir / filename

            # Download PDF
            response = requests.get(paper.pdf_url, stream=True)
            response.raise_for_status()

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"PDF downloaded: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Error downloading PDF {paper.id}: {e}")
            return None

    def extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """Extract text from a PDF file.

        Parameters
        ----------
        pdf_path:
            Path to the local PDF file.

        Returns
        -------
        str | None
            Extracted text or ``None`` on error.
        """
        try:
            with open(pdf_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""

                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n\n"

                logger.info(f"Text extracted from PDF: {len(text)} characters")
                return text.strip()

        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
            return None

    def get_paper_text_online(self, paper: ArxivPaper) -> Optional[str]:
        """Get article text online without downloading the PDF.

        Parameters
        ----------
        paper:
            The paper descriptor.

        Returns
        -------
        str | None
            The article text or ``None`` on error.
        """
        try:
            # First try to get through HTML version
            html_url = paper.abs_url.replace("/abs/", "/html/")

            response = requests.get(html_url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")

                # Find main text
                content_div = soup.find("div", class_="ltx_page_content")
                if content_div:
                    text = content_div.get_text(strip=True)
                    logger.info(f"Text obtained online (HTML): {len(text)} characters")
                    return text

            # If HTML not available, download and parse PDF
            logger.info("HTML version not available, downloading PDF...")
            pdf_path = self.download_pdf(paper)
            if pdf_path:
                text = self.extract_text_from_pdf(pdf_path)
                # Remove temporary file
                os.remove(pdf_path)
                return text

            return None

        except Exception as e:
            logger.error(f"Error getting text online {paper.id}: {e}")
            return None

    def search_by_author(
        self, author_name: str, max_results: int = 10
    ) -> List[ArxivPaper]:
        """
        Search articles by author

        Args:
            author_name: Author name
            max_results: Maximum number of results

        Returns:
            List of author's articles
        """
        query = f"au:{author_name}"
        return self.search_papers(query, max_results=max_results)

    def search_by_category(
        self, category: str, max_results: int = 10
    ) -> List[ArxivPaper]:
        """
        Search articles by category

        Args:
            category: Category (e.g., 'cs.AI', 'cs.LG')
            max_results: Maximum number of results

        Returns:
            List of articles in category
        """
        query = f"cat:{category}"
        return self.search_papers(query, max_results=max_results)

    def get_recent_papers(
        self, category: Optional[str] = None, days: int = 7, max_results: int = 10
    ) -> List[ArxivPaper]:
        """
        Get recent articles

        Args:
            category: Category filter
            days: Number of days back
            max_results: Maximum number of results

        Returns:
            List of recent articles
        """
        date_from = datetime.now() - timedelta(days=days)

        if category:
            query = f"cat:{category}"
        else:
            query = "*"

        return self.search_papers(
            query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            date_from=date_from,
        )

    def _build_search_query(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> str:
        """Build search query with filters"""

        search_parts = [query]

        # Add category filter
        if categories:
            cat_filter = " OR ".join([f"cat:{cat}" for cat in categories])
            search_parts.append(f"({cat_filter})")

        # Add date filter (basic support)
        if date_from:
            date_str = date_from.strftime("%Y%m%d")
            search_parts.append(f"submittedDate:[{date_str}* TO *]")

        return " AND ".join(search_parts)

    def _convert_to_arxiv_paper(self, result: arxiv.Result) -> ArxivPaper:
        """Convert search result to ArxivPaper"""

        return ArxivPaper(
            id=result.entry_id.split("/")[-1],
            title=result.title,
            authors=[author.name for author in result.authors],
            summary=result.summary,
            categories=result.categories,
            published=result.published,
            updated=result.updated,
            pdf_url=result.pdf_url or "",
            abs_url=result.entry_id,
            journal_ref=result.journal_ref,
            doi=result.doi,
            comment=result.comment,
            primary_category=result.primary_category,
        )

    def _clean_arxiv_id(self, arxiv_id: str) -> str:
        """Clean and normalize arXiv ID"""
        # Remove "arXiv:" prefix if present
        clean_id = arxiv_id.replace("arXiv:", "")
        # Remove version if present (e.g., v1, v2)
        clean_id = re.sub(r"v\d+$", "", clean_id)
        return clean_id


# Helper functions for convenience


def search_papers(query: str, max_results: int = 10) -> List[ArxivPaper]:
    """Quick article search"""
    parser = ArxivParser()
    return parser.search_papers(query, max_results)


def get_paper(arxiv_id: str) -> Optional[ArxivPaper]:
    """Quick article retrieval by ID"""
    parser = ArxivParser()
    return parser.get_paper_by_id(arxiv_id)


def download_paper(arxiv_id: str, downloads_dir: str = "downloads") -> Optional[str]:
    """Quick article download"""
    parser = ArxivParser(downloads_dir)
    paper = parser.get_paper_by_id(arxiv_id)
    if paper:
        return parser.download_pdf(paper)
    return None


if __name__ == "__main__":
    # Usage example
    logging.basicConfig(level=logging.INFO)

    parser = ArxivParser()

    # Search by keywords
    papers = parser.search_papers("machine learning transformers", max_results=5)

    for paper in papers:
        print(f"ID: {paper.id}")
        print(f"Title: {paper.title}")
        print(f"Authors: {', '.join(paper.authors)}")
        print(f"Published: {paper.published}")
        print(f"Categories: {', '.join(paper.categories)}")
        print("-" * 80)
