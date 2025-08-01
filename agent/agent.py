import asyncio
import os
import json
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared.database import (
    db, Task, ResearchTopic, UserSettings, ArxivPaper, PaperAnalysis, init_db
)
from peewee import DoesNotExist
from shared.llm import AGENT_MODEL
from shared.logger import get_logger
from shared.event_system import get_event_bus, Event, task_events
from shared.arxiv_parser import ArxivParser, ArxivPaper as ArxivPaperData
from agents import Agent, Runner

load_dotenv()

logger = get_logger(__name__)


class ArxivAnalysisAgent:
    """ИИ-агент для анализа научных статей arXiv"""
    
    def __init__(self):
        # Создаем агента для анализа области поиска
        self.area_analyzer = Agent(
            name="Area Relevance Analyzer",
            model=AGENT_MODEL,
            instructions="""
Ты эксперт по анализу научных статей. Твоя задача - определить, насколько статья относится к указанной научной области.

Анализируй:
1. Заголовок статьи
2. Аннотацию (abstract)
3. Категории arXiv
4. Ключевые слова

Оцени релевантность от 0 до 100%, где:
- 90-100%: статья полностью относится к области
- 70-89%: статья в основном относится к области
- 50-69%: статья частично относится к области  
- 30-49%: статья слабо связана с областью
- 0-29%: статья не относится к области

Ответь ТОЛЬКО числом (процентами) без дополнительного текста.
            """,
        )
        
        # Создаем агента для анализа целевой темы
        self.topic_analyzer = Agent(
            name="Target Topic Analyzer", 
            model=AGENT_MODEL,
            instructions="""
Ты эксперт по поиску специфических тем в научных статьях. Твоя задача - найти упоминания и применения целевой темы в тексте.

Анализируй:
1. Прямые упоминания темы
2. Синонимы и связанные термины
3. Методы и техники
4. Практическое применение

Оцени присутствие темы от 0 до 100%, где:
- 90-100%: тема является центральной в статье
- 70-89%: тема активно используется/обсуждается
- 50-69%: тема упоминается и применяется
- 30-49%: тема упоминается, но не является основной
- 0-29%: тема не упоминается или упоминается вскользь

Ответь ТОЛЬКО числом (процентами) без дополнительного текста.
            """,
        )
        
        # Создаем агента для генерации отчетов
        self.report_generator = Agent(
            name="Analysis Report Generator",
            model=AGENT_MODEL,
            instructions="""
Ты создаешь краткие аналитические отчеты о пересечении научных тем.

Сгенерируй краткий отчет (2-3 предложения) о том:
1. Как именно целевая тема применяется в контексте области поиска
2. Инновационность подхода
3. Практическая значимость

Используй профессиональный научный стиль, будь конкретным и информативным.
            """,
        )
        
        self.arxiv_parser = ArxivParser()
        self.monitoring_active = {}  # Отслеживание активных мониторингов по пользователям

    async def process_task(self, task: Task) -> str:
        """Обрабатывает задачи разных типов"""
        try:
            logger.info(f"Начинаю обработку задачи {task.id} типа {task.task_type}")
            
            task_data = json.loads(str(task.data)) if task.data else {}
            
            if task.task_type == "start_monitoring":
                return await self.start_monitoring(task_data)
            elif task.task_type == "restart_monitoring":
                return await self.restart_monitoring(task_data)
            else:
                return f"Неизвестный тип задачи: {task.task_type}"
                
        except Exception as e:
            error_msg = f"Ошибка обработки: {str(e)}"
            logger.error(f"Ошибка при обработке задачи {task.id}: {e}")
            return error_msg

    async def start_monitoring(self, task_data: Dict[str, Any]) -> str:
        """Запускает мониторинг arXiv для указанных тем"""
        try:
            user_id = task_data.get("user_id")
            topic_id = task_data.get("topic_id")
            target_topic = task_data.get("target_topic")
            search_area = task_data.get("search_area")
            
            if not all([user_id, topic_id, target_topic, search_area]):
                return "Ошибка: неполные данные для запуска мониторинга"
            
            logger.info(f"Запуск мониторинга для пользователя {user_id}: '{target_topic}' в '{search_area}'")
            
            # Помечаем мониторинг как активный
            self.monitoring_active[user_id] = {
                "topic_id": topic_id,
                "target_topic": target_topic,
                "search_area": search_area,
                "last_check": datetime.now()
            }
            
            # Запускаем начальный поиск статей
            if isinstance(user_id, int) and isinstance(target_topic, str) and isinstance(search_area, str) and isinstance(topic_id, int):
                await self.perform_arxiv_search(user_id, target_topic, search_area, topic_id)
            else:
                logger.error(f"Неверные типы параметров для perform_arxiv_search: {type(user_id)}, {type(target_topic)}, {type(search_area)}, {type(topic_id)}")
                return "Ошибка: неверные типы параметров"
            
            return f"Мониторинг запущен для тем: '{target_topic}' в области '{search_area}'"
            
        except Exception as e:
            logger.error(f"Ошибка при запуске мониторинга: {e}")
            return f"Ошибка при запуске мониторинга: {e}"

    async def restart_monitoring(self, task_data: Dict[str, Any]) -> str:
        """Перезапускает мониторинг с новыми параметрами"""
        # Останавливаем старый мониторинг
        user_id = task_data.get("user_id")
        if user_id in self.monitoring_active:
            del self.monitoring_active[user_id]
            
        # Запускаем новый
        return await self.start_monitoring(task_data)

    async def perform_arxiv_search(self, user_id: int, target_topic: str, search_area: str, topic_id: int):
        """Выполняет поиск статей на arXiv и анализирует их"""
        try:
            db.connect()
            
            # Получаем настройки пользователя
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
                days_back = int(settings.days_back_to_search)
            except (DoesNotExist, ValueError):
                days_back = 7
            
            # Этап 1: Поиск по области поиска
            logger.info(f"Этап 1: Поиск статей в области '{search_area}'")
            
            date_from = datetime.now() - timedelta(days=days_back)
            papers = self.arxiv_parser.search_papers(
                query=search_area,
                max_results=20,
                date_from=date_from
            )
            
            logger.info(f"Найдено {len(papers)} статей в области '{search_area}'")
            
            # Этап 2: Анализ каждой статьи на предмет целевой темы
            for paper in papers:
                await self.analyze_single_paper(paper, user_id, topic_id, target_topic, search_area)
                
            db.close()
            
        except Exception as e:
            logger.error(f"Ошибка при поиске arXiv: {e}")
            db.close()

    async def analyze_single_paper(self, paper_data: ArxivPaperData, user_id: int, topic_id: int, 
                                 target_topic: str, search_area: str):
        """Анализирует одну статью на соответствие темам"""
        try:
            # Проверяем, не анализировали ли уже эту статью
            try:
                existing_paper = ArxivPaper.get(ArxivPaper.arxiv_id == paper_data.id)
                
                # Проверяем, есть ли уже анализ для этой темы
                try:
                    existing_analysis = PaperAnalysis.get(
                        PaperAnalysis.paper == existing_paper.id,
                        PaperAnalysis.topic == topic_id
                    )
                    logger.info(f"Статья {paper_data.id} уже проанализирована для темы {topic_id}")
                    return
                except DoesNotExist:
                    paper = existing_paper
                    
            except DoesNotExist:
                # Сохраняем новую статью в БД
                paper = ArxivPaper.create(
                    arxiv_id=paper_data.id,
                    title=paper_data.title,
                    authors=json.dumps(paper_data.authors),
                    summary=paper_data.summary,
                    categories=json.dumps(paper_data.categories),
                    published=paper_data.published,
                    updated=paper_data.updated,
                    pdf_url=paper_data.pdf_url,
                    abs_url=paper_data.abs_url,
                    journal_ref=paper_data.journal_ref,
                    doi=paper_data.doi,
                    comment=paper_data.comment,
                    primary_category=paper_data.primary_category
                )
                logger.info(f"Сохранена новая статья: {paper_data.title}")
            
            # Подготавливаем данные для анализа
            paper_content = f"""
Заголовок: {paper_data.title}

Авторы: {', '.join(paper_data.authors)}

Аннотация: {paper_data.summary}

Категории: {', '.join(paper_data.categories)}

Основная категория: {paper_data.primary_category or 'Не указана'}
            """
            
            # Анализ релевантности области поиска
            area_query = f"Область поиска: {search_area}\n\nСтатья:\n{paper_content}"
            area_result = await Runner.run(self.area_analyzer, area_query)
            area_relevance = self._extract_percentage(str(area_result.final_output) if area_result.final_output else "0")
            
            # Анализ присутствия целевой темы
            topic_query = f"Целевая тема: {target_topic}\n\nСтатья:\n{paper_content}"
            topic_result = await Runner.run(self.topic_analyzer, topic_query)
            topic_relevance = self._extract_percentage(str(topic_result.final_output) if topic_result.final_output else "0")
            
            # Вычисляем интегральную оценку
            overall_relevance = (area_relevance * 0.4 + topic_relevance * 0.6)
            
            logger.info(f"Анализ {paper_data.id}: область={area_relevance}%, тема={topic_relevance}%, общая={overall_relevance}%")
            
            # Проверяем, достаточно ли релевантна статья
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
                min_overall = settings.min_overall_relevance
                min_area = settings.min_search_area_relevance
                min_topic = settings.min_target_topic_relevance
            except DoesNotExist:
                min_overall = 60.0
                min_area = 50.0
                min_topic = 50.0
            
            if (overall_relevance >= min_overall and 
                area_relevance >= min_area and 
                topic_relevance >= min_topic):
                
                # Генерируем подробный отчет
                report_query = f"""
Целевая тема: {target_topic}
Область поиска: {search_area}
Статья: {paper_data.title}

Аннотация: {paper_data.summary}

Оценки релевантности:
- Область поиска: {area_relevance}%
- Целевая тема: {topic_relevance}%
- Общая оценка: {overall_relevance:.1f}%

Создай краткий отчет о пересечении тем.
                """
                
                report_result = await Runner.run(self.report_generator, report_query)
                summary = str(report_result.final_output) if report_result.final_output else "Краткий анализ недоступен"
                
                # Сохраняем анализ
                analysis = PaperAnalysis.create(
                    paper=paper.id,
                    topic=topic_id,
                    search_area_relevance=area_relevance,
                    target_topic_relevance=topic_relevance,
                    overall_relevance=overall_relevance,
                    summary=summary,
                    status="analyzed"
                )
                
                logger.info(f"Создан анализ {analysis.id} для релевантной статьи {paper_data.id}")
                
                # Отправляем уведомление пользователю
                await self._send_analysis_notification(user_id, analysis.id, overall_relevance, settings)
                
        except Exception as e:
            logger.error(f"Ошибка при анализе статьи {paper_data.id}: {e}")

    async def _send_analysis_notification(self, user_id: int, analysis_id: int, relevance: float, settings: UserSettings):
        """Отправляет уведомление о найденной релевантной статье"""
        try:
            # Определяем тип уведомления
            if relevance >= settings.instant_notification_threshold:  # type: ignore
                # Мгновенное уведомление
                task = Task.create(
                    task_type="analysis_complete",
                    data=json.dumps({
                        "user_id": user_id,
                        "analysis_id": analysis_id,
                        "task_type": "analysis_complete"
                    }),
                    status="pending"
                )
                
                task_events.task_completed(
                    task_id=task.id,
                    result=f"analysis_complete:{analysis_id}"
                )
                
                logger.info(f"Отправлено мгновенное уведомление пользователю {user_id}")
                
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления: {e}")

    def _extract_percentage(self, text: str) -> float:
        """Извлекает процент из текста ответа ИИ"""
        try:
            # Ищем число followed by %
            match = re.search(r'(\d+(?:\.\d+)?)\s*%?', text.strip())
            if match:
                value = float(match.group(1))
                return min(100.0, max(0.0, value))  # Ограничиваем 0-100
            return 0.0
        except (ValueError, AttributeError):
            logger.warning(f"Не удалось извлечь процент из: {text}")
            return 0.0
