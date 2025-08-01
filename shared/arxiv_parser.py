"""
Модуль для работы с arXiv API
Предоставляет функции поиска, получения данных и загрузки научных статей
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
    """Класс для представления научной статьи с arXiv"""

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
    """Основной класс для работы с arXiv API"""

    def __init__(self, downloads_dir: str = "downloads"):
        """
        Инициализация парсера

        Args:
            downloads_dir: Директория для сохранения загруженных файлов
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
    ) -> List[ArxivPaper]:
        """
        Поиск статей по запросу

        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов
            sort_by: Критерий сортировки
            sort_order: Порядок сортировки
            categories: Фильтр по категориям (например, ['cs.AI', 'cs.LG'])
            date_from: Фильтр по дате (с)
            date_to: Фильтр по дате (до)

        Returns:
            Список объектов ArxivPaper
        """
        try:
            # Строим поисковый запрос
            search_query = self._build_search_query(
                query, categories, date_from, date_to
            )

            # Создаем поисковый объект
            search = arxiv.Search(
                query=search_query,
                max_results=max_results,
                sort_by=sort_by,
                sort_order=sort_order,
            )

            # Выполняем поиск
            results = []
            for result in self.client.results(search):
                paper = self._convert_to_arxiv_paper(result)
                results.append(paper)

            logger.info(f"Найдено {len(results)} статей по запросу: {query}")
            return results

        except Exception as e:
            logger.error(f"Ошибка при поиске статей: {e}")
            return []

    def get_paper_by_id(self, arxiv_id: str) -> Optional[ArxivPaper]:
        """
        Получение данных статьи по ID

        Args:
            arxiv_id: ID статьи на arXiv (например, "2301.07041")

        Returns:
            Объект ArxivPaper или None если не найдена
        """
        try:
            # Нормализуем ID
            clean_id = self._clean_arxiv_id(arxiv_id)

            # Создаем поисковый запрос по ID
            search = arxiv.Search(id_list=[clean_id])

            # Получаем результат
            results = list(self.client.results(search))
            if results:
                paper = self._convert_to_arxiv_paper(results[0])
                logger.info(f"Найдена статья: {paper.title}")
                return paper
            else:
                logger.warning(f"Статья с ID {arxiv_id} не найдена")
                return None

        except Exception as e:
            logger.error(f"Ошибка при получении статьи {arxiv_id}: {e}")
            return None

    def download_pdf(
        self, paper: ArxivPaper, filename: Optional[str] = None
    ) -> Optional[str]:
        """
        Загрузка PDF файла статьи

        Args:
            paper: Объект ArxivPaper
            filename: Имя файла для сохранения (по умолчанию генерируется автоматически)

        Returns:
            Путь к загруженному файлу или None при ошибке
        """
        try:
            if not filename:
                # Генерируем имя файла из ID и заголовка
                safe_title = re.sub(r"[^\w\s-]", "", paper.title)[:50]
                safe_title = re.sub(r"[-\s]+", "-", safe_title)
                filename = f"{paper.id}_{safe_title}.pdf"

            filepath = self.downloads_dir / filename

            # Загружаем PDF
            response = requests.get(paper.pdf_url, stream=True)
            response.raise_for_status()

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"PDF загружен: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Ошибка при загрузке PDF {paper.id}: {e}")
            return None

    def extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """
        Извлечение текста из PDF файла

        Args:
            pdf_path: Путь к PDF файлу

        Returns:
            Извлеченный текст или None при ошибке
        """
        try:
            with open(pdf_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""

                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n\n"

                logger.info(f"Текст извлечен из PDF: {len(text)} символов")
                return text.strip()

        except Exception as e:
            logger.error(f"Ошибка при извлечении текста из PDF {pdf_path}: {e}")
            return None

    def get_paper_text_online(self, paper: ArxivPaper) -> Optional[str]:
        """
        Получение полного текста статьи онлайн без загрузки PDF

        Args:
            paper: Объект ArxivPaper

        Returns:
            Текст статьи или None при ошибке
        """
        try:
            # Сначала пробуем получить через HTML версию
            html_url = paper.abs_url.replace("/abs/", "/html/")

            response = requests.get(html_url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")

                # Ищем основной текст
                content_div = soup.find("div", class_="ltx_page_content")
                if content_div:
                    text = content_div.get_text(strip=True)
                    logger.info(f"Текст получен онлайн (HTML): {len(text)} символов")
                    return text

            # Если HTML не доступен, загружаем и парсим PDF
            logger.info("HTML версия недоступна, загружаем PDF...")
            pdf_path = self.download_pdf(paper)
            if pdf_path:
                text = self.extract_text_from_pdf(pdf_path)
                # Удаляем временный файл
                os.remove(pdf_path)
                return text

            return None

        except Exception as e:
            logger.error(f"Ошибка при получении текста онлайн {paper.id}: {e}")
            return None

    def search_by_author(
        self, author_name: str, max_results: int = 10
    ) -> List[ArxivPaper]:
        """
        Поиск статей по автору

        Args:
            author_name: Имя автора
            max_results: Максимальное количество результатов

        Returns:
            Список статей автора
        """
        query = f"au:{author_name}"
        return self.search_papers(query, max_results=max_results)

    def search_by_category(
        self, category: str, max_results: int = 10
    ) -> List[ArxivPaper]:
        """
        Поиск статей по категории

        Args:
            category: Категория (например, 'cs.AI', 'cs.LG')
            max_results: Максимальное количество результатов

        Returns:
            Список статей в категории
        """
        query = f"cat:{category}"
        return self.search_papers(query, max_results=max_results)

    def get_recent_papers(
        self, category: Optional[str] = None, days: int = 7, max_results: int = 10
    ) -> List[ArxivPaper]:
        """
        Получение последних статей

        Args:
            category: Категория для фильтра
            days: Количество дней назад
            max_results: Максимальное количество результатов

        Returns:
            Список последних статей
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
        """Построение поискового запроса с фильтрами"""

        search_parts = [query]

        # Добавляем фильтр по категориям
        if categories:
            cat_filter = " OR ".join([f"cat:{cat}" for cat in categories])
            search_parts.append(f"({cat_filter})")

        # Добавляем фильтр по датам (базовая поддержка)
        if date_from:
            date_str = date_from.strftime("%Y%m%d")
            search_parts.append(f"submittedDate:[{date_str}* TO *]")

        return " AND ".join(search_parts)

    def _convert_to_arxiv_paper(self, result: arxiv.Result) -> ArxivPaper:
        """Конвертация результата поиска в ArxivPaper"""

        return ArxivPaper(
            id=result.entry_id.split("/")[-1],
            title=result.title,
            authors=[author.name for author in result.authors],
            summary=result.summary,
            categories=result.categories,
            published=result.published,
            updated=result.updated,
            pdf_url=result.pdf_url,
            abs_url=result.entry_id,
            journal_ref=result.journal_ref,
            doi=result.doi,
            comment=result.comment,
            primary_category=result.primary_category,
        )

    def _clean_arxiv_id(self, arxiv_id: str) -> str:
        """Очистка и нормализация arXiv ID"""
        # Убираем префикс "arXiv:" если есть
        clean_id = arxiv_id.replace("arXiv:", "")
        # Убираем версию если есть (например, v1, v2)
        clean_id = re.sub(r"v\d+$", "", clean_id)
        return clean_id


# Вспомогательные функции для удобства использования


def search_papers(query: str, max_results: int = 10) -> List[ArxivPaper]:
    """Быстрый поиск статей"""
    parser = ArxivParser()
    return parser.search_papers(query, max_results)


def get_paper(arxiv_id: str) -> Optional[ArxivPaper]:
    """Быстрое получение статьи по ID"""
    parser = ArxivParser()
    return parser.get_paper_by_id(arxiv_id)


def download_paper(arxiv_id: str, downloads_dir: str = "downloads") -> Optional[str]:
    """Быстрая загрузка статьи"""
    parser = ArxivParser(downloads_dir)
    paper = parser.get_paper_by_id(arxiv_id)
    if paper:
        return parser.download_pdf(paper)
    return None


if __name__ == "__main__":
    # Пример использования
    logging.basicConfig(level=logging.INFO)

    parser = ArxivParser()

    # Поиск по ключевым словам
    papers = parser.search_papers("machine learning transformers", max_results=5)

    for paper in papers:
        print(f"ID: {paper.id}")
        print(f"Title: {paper.title}")
        print(f"Authors: {', '.join(paper.authors)}")
        print(f"Published: {paper.published}")
        print(f"Categories: {', '.join(paper.categories)}")
        print("-" * 80)
