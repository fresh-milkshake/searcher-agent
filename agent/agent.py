import os
import json
import re
import asyncio
from datetime import datetime
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
    ResearchTopic,
)
from peewee import DoesNotExist
from shared.llm import AGENT_MODEL
from shared.logger import get_logger
from shared.event_system import task_events
from shared.arxiv_parser import ArxivParser, ArxivPaper as ArxivPaperData
from agents import Agent, Runner
from agent.schemas import TopicAnalysis, AnalysisReport

load_dotenv()

logger = get_logger(__name__)


class ArxivAnalysisAgent:
    """AI agent for analyzing arXiv scientific articles"""

    def __init__(self):
        logger.debug("Initializing ArxivAnalysisAgent")
        # Create agent for target topic analysis
        self.topic_analyzer = Agent(
            name="Target Topic Analyzer",
            model=AGENT_MODEL,
            output_type=TopicAnalysis,
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

IMPORTANT: Always return valid JSON without any line breaks or special characters in string values. Keep reasoning under 100 characters.

Provide your assessment with confidence level, key mentions found, and concise reasoning.
            """,
        )

        # Create agent for report generation
        self.report_generator = Agent(
            name="Analysis Report Generator",
            model=AGENT_MODEL,
            output_type=AnalysisReport,
            instructions="""
You create concise analytical reports on the intersection of scientific topics.

Analyze and provide:
1. How exactly the target topic is applied in the context of the search area
2. The innovativeness of the approach
3. Practical significance
4. Key applications or methods mentioned
5. Overall recommendation for relevance

IMPORTANT: Always return valid JSON without any line breaks or special characters in string values. Keep summary under 300 characters.

Use a professional scientific style, be specific and concise.
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
            elif task.task_type == "analysis_complete":
                logger.debug("Task type: analysis_complete - notification task")
                return "Analysis notification processed"
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
                f"Starting monitoring for user {user_id}: '{target_topic}' in area '{search_area}'",
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

            # Start continuous monitoring
            if (
                isinstance(user_id, int)
                and isinstance(target_topic, str)
                and isinstance(search_area, str)
                and isinstance(topic_id, int)
            ):
                logger.debug(
                    "Parameters for continuous monitoring are valid, starting monitoring loop"
                )
                # Start continuous monitoring in background
                asyncio.create_task(
                    self._continuous_monitoring_loop(
                        user_id, target_topic, search_area, topic_id
                    )
                )
            else:
                logger.error(
                    f"Invalid parameter types for continuous monitoring: {type(user_id)}, {type(target_topic)}, {type(search_area)}, {type(topic_id)}"
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

    async def _continuous_monitoring_loop(
        self, user_id: int, target_topic: str, search_area: str, topic_id: int
    ):
        """Continuous monitoring loop that runs until stopped by user"""
        logger.info(f"Starting continuous monitoring loop for user {user_id}")

        search_offset = 0  # Track position in search results

        while True:
            try:
                # Check if monitoring is still active for this user
                if user_id not in self.monitoring_active:
                    logger.info(f"Monitoring stopped for user {user_id}")
                    break

                # Check if user has paused monitoring
                try:
                    settings = UserSettings.get(UserSettings.user_id == user_id)
                    if not settings.monitoring_enabled:
                        logger.info(f"Monitoring paused for user {user_id}, waiting...")
                        await asyncio.sleep(60)  # Wait 1 minute before checking again
                        continue
                except DoesNotExist:
                    pass

                # Check if topic is still active
                try:
                    topic = ResearchTopic.get(
                        ResearchTopic.id == topic_id, ResearchTopic.is_active
                    )
                    if not topic.is_active:
                        logger.info(
                            f"Topic {topic_id} is no longer active for user {user_id}"
                        )
                        break
                except DoesNotExist:
                    logger.info(f"Topic {topic_id} no longer exists for user {user_id}")
                    break

                logger.info(
                    f"Performing search cycle {search_offset//20 + 1} for user {user_id}"
                )
                await self.perform_arxiv_search_with_offset(
                    user_id, target_topic, search_area, topic_id, search_offset
                )

                search_offset += 20  # Move to next batch

                # Wait between search cycles to avoid overloading and rate limiting
                await asyncio.sleep(60)  # Wait 60 seconds between cycles to avoid rate limits

            except Exception as e:
                logger.error(
                    f"Error in continuous monitoring loop for user {user_id}: {e}"
                )
                # Don't break the loop on errors, just wait and continue
                await asyncio.sleep(60)  # Wait longer on error
                continue

        logger.info(f"Continuous monitoring loop ended for user {user_id}")

    async def perform_arxiv_search(
        self, user_id: int, target_topic: str, search_area: str, topic_id: int
    ):
        """Performs arXiv search and analyzes articles (legacy function for compatibility)"""
        await self.perform_arxiv_search_with_offset(
            user_id, target_topic, search_area, topic_id, 0
        )

    async def perform_arxiv_search_with_offset(
        self,
        user_id: int,
        target_topic: str,
        search_area: str,
        topic_id: int,
        offset: int = 0,
    ):
        """Performs arXiv search with pagination support"""
        try:
            cycle_num = offset // 20 + 1
            self.update_status(
                "searching_papers",
                f"Search cycle {cycle_num}: Searching papers on topic '{target_topic}' in area '{search_area}' for user {user_id}",
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

            # Stage 1: Search by search area with offset
            logger.info(
                f"Stage 1 (cycle {cycle_num}): Searching articles in area '{search_area}' with offset {offset}"
            )

            # Use offset for pagination
            papers = self.arxiv_parser.search_papers(
                query=search_area,
                max_results=20,
                start=offset,  # Add offset parameter for pagination
            )

            logger.info(
                f"Found {len(papers)} articles in area '{search_area}' (cycle {cycle_num})"
            )

            if len(papers) == 0:
                logger.info(
                    f"No more articles found, reached end of search results for cycle {cycle_num}"
                )
                return

            self.update_status(
                "analyzing_papers",
                f"Cycle {cycle_num}: Analyzing {len(papers)} papers for user {user_id}",
                user_id,
                topic_id,
            )

            # Stage 2: Analyze each article for target topic
            for idx, paper in enumerate(papers):
                logger.debug(
                    f"Analyzing article {idx+1}/{len(papers)} (cycle {cycle_num}): {getattr(paper, 'id', 'unknown id')}"
                )
                self.update_status(
                    "analyzing_paper",
                    f"Cycle {cycle_num}: Analyzing paper {idx+1}/{len(papers)}: {getattr(paper, 'title', 'unknown title')[:50]}...",
                    user_id,
                    topic_id,
                )
                await self.analyze_single_paper(
                    paper, user_id, topic_id, target_topic, search_area
                )
                
                # Add delay between articles to avoid rate limiting
                if idx < len(papers) - 1:  # Don't delay after the last article
                    await asyncio.sleep(2)  # 2 second delay between articles

            logger.info(f"Completed analysis cycle {cycle_num} for user {user_id}")
            logger.debug(
                "Database connection maintained after search and article analysis"
            )
            # Don't close connection here - let the caller manage it

        except Exception as e:
            logger.error(f"Error in arXiv search (cycle {cycle_num}): {e}")
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

            # Analyze target topic presence (area relevance is assumed since we search by keywords)
            topic_query = f"Target topic: {target_topic}\n\nArticle:\n{paper_content}"
            logger.debug(f"Sending topic_analyzer request for article {paper_data.id}")
            topic_result = await self._run_llm_with_retry(self.topic_analyzer, topic_query)
            logger.debug(f"topic_analyzer result: {topic_result.final_output}")
            logger.info(
                f"AI response (topic_analyzer) for article {paper_data.id}: {topic_result.final_output}"
            )

            # Extract structured output
            if isinstance(topic_result.final_output, TopicAnalysis):
                topic_relevance = topic_result.final_output.topic_presence
                topic_confidence = topic_result.final_output.confidence
                key_mentions = topic_result.final_output.key_mentions
                logger.info(
                    f"Topic analysis: {topic_relevance}% (confidence: {topic_confidence}, mentions: {len(key_mentions)})"
                )
            else:
                # Fallback for non-structured output
                topic_relevance = self._extract_percentage(
                    str(topic_result.final_output) if topic_result.final_output else "0"
                )
                topic_confidence = "unknown"
                key_mentions = []

            # Use topic relevance as overall relevance (area is pre-filtered by search)
            overall_relevance = topic_relevance

            logger.info(
                f"Analysis {paper_data.id}: topic={topic_relevance}% ({topic_confidence}), overall={overall_relevance}%"
            )

            # Check if article is relevant enough
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
                min_topic = settings.min_target_topic_relevance
                logger.debug(f"Threshold value: min_topic={min_topic}")
            except DoesNotExist:
                min_topic = 50.0
                logger.warning(
                    f"Failed to get user {user_id} settings, using default min_topic=50.0"
                )

            if topic_relevance >= min_topic:
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
- Target topic: {topic_relevance}%
- Overall score: {overall_relevance:.1f}%

Create a brief report on topic intersection.
                """

                logger.debug(
                    f"Sending report_generator request for article {paper_data.id}"
                )
                report_result = await self._run_llm_with_retry(self.report_generator, report_query)
                logger.debug(f"report_generator result: {report_result.final_output}")
                logger.info(
                    f"AI response (report_generator) for article {paper_data.id}: {report_result.final_output}"
                )

                # Extract structured output
                if isinstance(report_result.final_output, AnalysisReport):
                    summary = report_result.final_output.summary
                    innovation_level = report_result.final_output.innovation_level
                    practical_significance = (
                        report_result.final_output.practical_significance
                    )
                    recommendation = report_result.final_output.recommendation
                    logger.info(
                        f"Report generated: innovation={innovation_level}, significance={practical_significance}, recommendation={recommendation}"
                    )
                else:
                    # Fallback for non-structured output
                    summary = (
                        str(report_result.final_output)
                        if report_result.final_output
                        else "Brief analysis unavailable"
                    )
                    innovation_level = "unknown"
                    practical_significance = "unknown"
                    recommendation = "not_assessed"

                # Save analysis
                logger.info(
                    f"Saving analysis for article {paper_data.id} and topic {topic_id}"
                )
                analysis = PaperAnalysis.create(
                    paper=paper.id,
                    topic=topic_id,
                    search_area_relevance=100.0,  # Pre-filtered by search keywords
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
                    f"Article {paper_data.id} did not meet relevance threshold: topic={topic_relevance}%, overall={overall_relevance}%"
                )

        except Exception as e:
            logger.error(f"Error analyzing article {paper_data.id}: {e}")
            # Don't re-raise the exception to avoid stopping the entire monitoring loop
            # Just log the error and continue with the next article

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

    async def _run_llm_with_retry(self, agent, query: str, max_retries: int = 3, base_delay: float = 2.0):
        """Run LLM with retry logic for rate limiting and other transient errors"""
        for attempt in range(max_retries):
            try:
                result = await Runner.run(agent, query)
                return result
            except Exception as e:
                error_str = str(e).lower()
                
                # Check if it's a rate limit error
                if "rate limit" in error_str or "429" in error_str:
                    if attempt < max_retries - 1:
                        # Calculate exponential backoff delay
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Rate limit exceeded after {max_retries} attempts: {e}")
                        raise
                
                # Check if it's a JSON parsing error
                elif "json" in error_str and ("invalid" in error_str or "parse" in error_str):
                    if attempt < max_retries - 1:
                        logger.warning(f"JSON parsing error, retrying (attempt {attempt + 1}/{max_retries}): {e}")
                        await asyncio.sleep(1)
                        continue
                    else:
                        logger.error(f"JSON parsing failed after {max_retries} attempts: {e}")
                        raise
                
                # For other errors, don't retry
                else:
                    logger.error(f"Non-retryable error: {e}")
                    raise
        
        raise Exception(f"Failed after {max_retries} attempts")

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
