import os
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared.database import (
    db,
    Task,
    UserSettings,
    ArxivPaper,
    PaperAnalysis,
    AgentStatus,
)
from peewee import DoesNotExist
from shared.llm import AGENT_MODEL
from shared.logger import get_logger
from shared.event_system import task_events
from shared.arxiv_parser import ArxivParser, ArxivPaper as ArxivPaperData
from agents import Agent, Runner

load_dotenv()

logger = get_logger(__name__)


class ArxivAnalysisAgent:
    """AI agent for analyzing arXiv scientific articles"""

    def __init__(self):
        logger.debug("Initializing ArxivAnalysisAgent")
        # Create agent for search area analysis
        self.area_analyzer = Agent(
            name="Area Relevance Analyzer",
            model=AGENT_MODEL,
            instructions="""
You are an expert in analyzing scientific articles. Your task is to determine how relevant an article is to the specified scientific field.

Analyze:
1. The article title
2. The abstract
3. arXiv categories
4. Keywords

Assess the relevance from 0 to 100%, where:
- 90-100%: the article fully belongs to the field
- 70-89%: the article mostly belongs to the field
- 50-69%: the article is partially related to the field
- 30-49%: the article is weakly related to the field
- 0-29%: the article does not belong to the field

Reply ONLY with a number (percentage), no additional text.
            """,
        )

        # Create agent for target topic analysis
        self.topic_analyzer = Agent(
            name="Target Topic Analyzer",
            model=AGENT_MODEL,
            instructions="""
You are an expert in identifying specific topics in scientific articles. Your task is to find mentions and applications of the target topic in the text.

Analyze:
1. Direct mentions of the topic
2. Synonyms and related terms
3. Methods and techniques
4. Practical applications

Assess the presence of the topic from 0 to 100%, where:
- 90-100%: the topic is central to the article
- 70-89%: the topic is actively used/discussed
- 50-69%: the topic is mentioned and applied
- 30-49%: the topic is mentioned but not central
- 0-29%: the topic is not mentioned or only briefly mentioned

Reply ONLY with a number (percentage), no additional text.
            """,
        )

        # Create agent for report generation
        self.report_generator = Agent(
            name="Analysis Report Generator",
            model=AGENT_MODEL,
            instructions="""
You create concise analytical reports on the intersection of scientific topics.

Generate a brief report (2-3 sentences) about:
1. How exactly the target topic is applied in the context of the search area
2. The innovativeness of the approach
3. Practical significance

Use a professional scientific style, be specific and informative.
            """,
        )

        self.arxiv_parser = ArxivParser()
        self.monitoring_active = {}  # Tracking active monitoring by users
        self.agent_id = "main_agent"
        self.papers_processed_session = 0
        self.papers_found_session = 0
        logger.debug("ArxivAnalysisAgent successfully initialized")

    async def process_task(self, task: Task) -> str:
        """Processes different types of tasks"""
        try:
            logger.info(f"Starting to process task {task.id} of type {task.task_type}")

            task_data = json.loads(str(task.data)) if task.data else {}
            logger.debug(f"Task data: {task_data}")

            if task.task_type == "start_monitoring":
                logger.debug("Task type: start_monitoring")
                return await self.start_monitoring(task_data)
            elif task.task_type == "restart_monitoring":
                logger.debug("Task type: restart_monitoring")
                return await self.restart_monitoring(task_data)
            else:
                logger.warning(f"Unknown task type: {task.task_type}")
                return f"Unknown task type: {task.task_type}"

        except Exception as e:
            error_msg = f"Processing error: {str(e)}"
            logger.error(f"Error processing task {task.id}: {e}")
            return error_msg

    async def start_monitoring(self, task_data: Dict[str, Any]) -> str:
        """Starts arXiv monitoring for specified topics"""
        try:
            logger.debug(f"Input data for start_monitoring: {task_data}")
            user_id = task_data.get("user_id")
            topic_id = task_data.get("topic_id")
            target_topic = task_data.get("target_topic")
            search_area = task_data.get("search_area")

            if not all([user_id, topic_id, target_topic, search_area]):
                logger.error("Error: incomplete data for starting monitoring")
                return "Error: incomplete data for starting monitoring"

            self.update_status(
                "starting_monitoring",
                f"Запуск мониторинга для пользователя {user_id}: '{target_topic}' в области '{search_area}'",
                user_id,
                topic_id,
            )

            logger.info(
                f"Starting monitoring for user {user_id}: '{target_topic}' in '{search_area}'"
            )

            # Mark monitoring as active
            self.monitoring_active[user_id] = {
                "topic_id": topic_id,
                "target_topic": target_topic,
                "search_area": search_area,
                "last_check": datetime.now(),
            }
            logger.debug(
                f"monitoring_active[{user_id}] = {self.monitoring_active[user_id]}"
            )

            # Start initial article search
            if (
                isinstance(user_id, int)
                and isinstance(target_topic, str)
                and isinstance(search_area, str)
                and isinstance(topic_id, int)
            ):
                logger.debug(
                    "Parameters for perform_arxiv_search are valid, starting search"
                )
                await self.perform_arxiv_search(
                    user_id, target_topic, search_area, topic_id
                )
            else:
                logger.error(
                    f"Invalid parameter types for perform_arxiv_search: {type(user_id)}, {type(target_topic)}, {type(search_area)}, {type(topic_id)}"
                )
                return "Error: invalid parameter types"

            logger.info(
                f"Monitoring successfully started for topics: '{target_topic}' in area '{search_area}'"
            )
            return f"Monitoring started for topics: '{target_topic}' in area '{search_area}'"

        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
            return f"Error starting monitoring: {e}"

    async def restart_monitoring(self, task_data: Dict[str, Any]) -> str:
        """Restarts monitoring with new parameters"""
        logger.debug(f"Restarting monitoring with data: {task_data}")
        # Stop old monitoring
        user_id = task_data.get("user_id")
        if user_id in self.monitoring_active:
            logger.info(f"Stopping old monitoring for user {user_id}")
            del self.monitoring_active[user_id]

        # Start new monitoring
        logger.info(f"Starting new monitoring for user {user_id}")
        return await self.start_monitoring(task_data)

    async def perform_arxiv_search(
        self, user_id: int, target_topic: str, search_area: str, topic_id: int
    ):
        """Performs arXiv search and analyzes articles"""
        try:
            self.update_status(
                "searching_papers",
                f"Поиск статей по теме '{target_topic}' в области '{search_area}' для пользователя {user_id}",
                user_id,
                topic_id,
            )

            logger.debug(f"Checking database connection for user {user_id}")
            # Check if database is already connected
            if hasattr(db, "is_closed") and db.is_closed():
                db.connect()

            # Get user settings
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
                days_back = int(settings.days_back_to_search)
                logger.debug(
                    f"User {user_id} settings: days_back_to_search={days_back}"
                )
            except (DoesNotExist, ValueError):
                days_back = 7
                logger.warning(
                    f"Failed to get user {user_id} settings, using days_back=7"
                )

            # Stage 1: Search by search area
            logger.info(f"Stage 1: Searching articles in area '{search_area}'")

            # Remove date filter to ensure we find articles
            # date_from = datetime.now() - timedelta(days=days_back)
            # logger.debug(f"Search start date: {date_from}")
            papers = self.arxiv_parser.search_papers(
                query=search_area,
                max_results=20,  # Removed date_from parameter
            )

            logger.info(f"Found {len(papers)} articles in area '{search_area}'")

            self.update_status(
                "analyzing_papers",
                f"Анализ {len(papers)} статей для пользователя {user_id}",
                user_id,
                topic_id,
            )

            # Stage 2: Analyze each article for target topic
            for idx, paper in enumerate(papers):
                logger.debug(
                    f"Analyzing article {idx+1}/{len(papers)}: {getattr(paper, 'id', 'unknown id')}"
                )
                self.update_status(
                    "analyzing_paper",
                    f"Анализ статьи {idx+1}/{len(papers)}: {getattr(paper, 'title', 'unknown title')[:50]}...",
                    user_id,
                    topic_id,
                )
                await self.analyze_single_paper(
                    paper, user_id, topic_id, target_topic, search_area
                )

            logger.debug(
                "Database connection maintained after search and article analysis"
            )
            # Don't close connection here - let the caller manage it

        except Exception as e:
            logger.error(f"Error in arXiv search: {e}")
            # Don't close connection in exception handler either

    async def analyze_single_paper(
        self,
        paper_data: ArxivPaperData,
        user_id: int,
        topic_id: int,
        target_topic: str,
        search_area: str,
    ):
        """Analyzes a single article for topic relevance"""
        try:
            self.increment_papers_processed()
            logger.debug(
                f"Starting analysis of article {paper_data.id} for user {user_id}, topic_id={topic_id}"
            )
            # Check if we've already analyzed this article
            try:
                existing_paper = ArxivPaper.get(ArxivPaper.arxiv_id == paper_data.id)
                logger.debug(f"Article {paper_data.id} already exists in database")

                # Check if there's already an analysis for this topic
                try:
                    PaperAnalysis.get(
                        PaperAnalysis.paper == existing_paper.id,
                        PaperAnalysis.topic == topic_id,
                    )
                    logger.info(
                        f"Article {paper_data.id} already analyzed for topic {topic_id}"
                    )
                    return
                except DoesNotExist:
                    logger.debug(
                        f"No analysis yet for article {paper_data.id} and topic {topic_id}"
                    )
                    paper = existing_paper

            except DoesNotExist:
                # Save new article to database
                logger.info(f"Saving new article {paper_data.id} to database")
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
                    primary_category=paper_data.primary_category,
                )
                logger.info(f"New article saved: {paper_data.title}")

            # Prepare data for analysis
            paper_content = f"""
Title: {paper_data.title}

Authors: {', '.join(paper_data.authors)}

Abstract: {paper_data.summary}

Categories: {', '.join(paper_data.categories)}

Primary category: {paper_data.primary_category or 'Not specified'}
            """
            logger.debug(f"Content prepared for analysis of article {paper_data.id}")

            # Analyze search area relevance
            area_query = f"Search area: {search_area}\n\nArticle:\n{paper_content}"
            logger.debug(f"Sending area_analyzer request for article {paper_data.id}")
            area_result = await Runner.run(self.area_analyzer, area_query)
            logger.debug(f"area_analyzer result: {area_result.final_output}")
            logger.info(
                f"AI response (area_analyzer) for article {paper_data.id}: {area_result.final_output}"
            )
            area_relevance = self._extract_percentage(
                str(area_result.final_output) if area_result.final_output else "0"
            )

            # Analyze target topic presence
            topic_query = f"Target topic: {target_topic}\n\nArticle:\n{paper_content}"
            logger.debug(f"Sending topic_analyzer request for article {paper_data.id}")
            topic_result = await Runner.run(self.topic_analyzer, topic_query)
            logger.debug(f"topic_analyzer result: {topic_result.final_output}")
            logger.info(
                f"AI response (topic_analyzer) for article {paper_data.id}: {topic_result.final_output}"
            )
            topic_relevance = self._extract_percentage(
                str(topic_result.final_output) if topic_result.final_output else "0"
            )

            # Calculate overall relevance score
            overall_relevance = area_relevance * 0.4 + topic_relevance * 0.6

            logger.info(
                f"Analysis {paper_data.id}: area={area_relevance}%, topic={topic_relevance}%, overall={overall_relevance}%"
            )

            # Check if article is relevant enough
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
                min_overall = settings.min_overall_relevance
                min_area = settings.min_search_area_relevance
                min_topic = settings.min_target_topic_relevance
                logger.debug(
                    f"Threshold values: min_overall={min_overall}, min_area={min_area}, min_topic={min_topic}"
                )
            except DoesNotExist:
                min_overall = 60.0
                min_area = 50.0
                min_topic = 50.0
                logger.warning(
                    f"Failed to get user {user_id} settings, using default values"
                )

            if (
                overall_relevance >= min_overall
                and area_relevance >= min_area
                and topic_relevance >= min_topic
            ):
                logger.info(
                    f"Article {paper_data.id} meets all relevance criteria, generating report"
                )
                # Generate detailed report
                report_query = f"""
Target topic: {target_topic}
Search area: {search_area}
Article: {paper_data.title}

Abstract: {paper_data.summary}

Relevance scores:
- Search area: {area_relevance}%
- Target topic: {topic_relevance}%
- Overall score: {overall_relevance:.1f}%

Create a brief report on topic intersection.
                """

                logger.debug(
                    f"Sending report_generator request for article {paper_data.id}"
                )
                report_result = await Runner.run(self.report_generator, report_query)
                logger.debug(f"report_generator result: {report_result.final_output}")
                logger.info(
                    f"AI response (report_generator) for article {paper_data.id}: {report_result.final_output}"
                )
                summary = (
                    str(report_result.final_output)
                    if report_result.final_output
                    else "Brief analysis unavailable"
                )

                # Save analysis
                logger.info(
                    f"Saving analysis for article {paper_data.id} and topic {topic_id}"
                )
                analysis = PaperAnalysis.create(
                    paper=paper.id,
                    topic=topic_id,
                    search_area_relevance=area_relevance,
                    target_topic_relevance=topic_relevance,
                    overall_relevance=overall_relevance,
                    summary=summary,
                    status="analyzed",
                )

                self.increment_papers_found()

                logger.info(
                    f"Created analysis {analysis.id} for relevant article {paper_data.id}"
                )

                # Send notification to user
                await self._send_analysis_notification(
                    user_id, analysis.id, overall_relevance, settings
                )
            else:
                logger.info(
                    f"Article {paper_data.id} did not meet relevance threshold: overall={overall_relevance}, area={area_relevance}, topic={topic_relevance}"
                )

        except Exception as e:
            logger.error(f"Error analyzing article {paper_data.id}: {e}")

    async def _send_analysis_notification(
        self, user_id: int, analysis_id: int, relevance: float, settings: UserSettings
    ):
        """Sends notification about found relevant article"""
        try:
            logger.debug(
                f"Checking need for instant notification for user {user_id}, relevance={relevance}, threshold={settings.instant_notification_threshold}"
            )
            # Determine notification type
            if relevance >= settings.instant_notification_threshold:  # type: ignore
                # Instant notification
                logger.info(
                    f"Creating task for instant notification for user {user_id}"
                )
                task = Task.create(
                    task_type="analysis_complete",
                    data=json.dumps(
                        {
                            "user_id": user_id,
                            "analysis_id": analysis_id,
                            "task_type": "analysis_complete",
                        }
                    ),
                    status="pending",
                )

                logger.debug(f"Executing task_completed event for task {task.id}")
                task_events.task_completed(
                    task_id=task.id, result=f"analysis_complete:{analysis_id}"
                )

                logger.info(f"Instant notification sent to user {user_id}")

        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    def update_status(
        self,
        status: str,
        activity: str,
        user_id: Optional[int] = None,
        topic_id: Optional[int] = None,
    ):
        """Update agent status in database"""
        try:
            # Check if database is already connected
            if hasattr(db, "is_closed") and db.is_closed():
                db.connect()

            # Get or create agent status record
            agent_status, created = AgentStatus.get_or_create(
                agent_id=self.agent_id,
                defaults={
                    "status": status,
                    "activity": activity,
                    "current_user_id": user_id,
                    "current_topic_id": topic_id,
                    "papers_processed": self.papers_processed_session,
                    "papers_found": self.papers_found_session,
                    "session_start": datetime.now(),
                },
            )

            if not created:
                agent_status.status = status
                agent_status.activity = activity
                agent_status.current_user_id = user_id
                agent_status.current_topic_id = topic_id
                agent_status.papers_processed = self.papers_processed_session
                agent_status.papers_found = self.papers_found_session
                agent_status.last_activity = datetime.now()
                agent_status.updated_at = datetime.now()
                agent_status.save()

            logger.debug(f"Agent status updated: {status} - {activity}")

            # Don't close connection here - let the caller manage it
        except Exception as e:
            logger.error(f"Error updating agent status: {e}")
            # Don't close connection in exception handler either

    def increment_papers_processed(self):
        """Increment processed papers counter"""
        self.papers_processed_session += 1

    def increment_papers_found(self):
        """Increment found papers counter"""
        self.papers_found_session += 1

    def _extract_percentage(self, text: str) -> float:
        """Extracts percentage from AI response text"""
        try:
            logger.debug(f"Extracting percentage from text: '{text}'")
            # Look for number followed by %
            match = re.search(r"(\d+(?:\.\d+)?)\s*%?", text.strip())
            if match:
                value = float(match.group(1))
                logger.debug(f"Extracted percentage value: {value}")
                return min(100.0, max(0.0, value))  # Limit to 0-100
            logger.warning(f"Percentage not found in text: '{text}'")
            return 0.0
        except (ValueError, AttributeError):
            logger.warning(f"Failed to extract percentage from: {text}")
            return 0.0
