import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared.database import db, Task, ResearchTopic, UserSettings, init_db
from peewee import DoesNotExist
from shared.logger import get_logger
from shared.event_system import get_event_bus, Event, task_events
from agent.agent import ArxivAnalysisAgent

load_dotenv()

logger = get_logger(__name__)


async def handle_task_creation(event: Event):
    """Handler for creating new tasks - processes tasks as they arrive"""
    try:
        logger.debug(f"handle_task_creation called with event: {event.data}")
        task_id = event.data.get("task_id") if event.data else None
        task_type = event.data.get("task_type") if event.data else None

        if not task_id:
            logger.warning(f"Received task creation event without ID: {event.data}")
            return

        logger.info(
            f"🚀 arXiv AGENT: Received notification about new task {task_id} of type {task_type}"
        )

        # Check if database is already connected
        if hasattr(db, "is_closed") and db.is_closed():
            db.connect()
        logger.debug("Database connection established (handle_task_creation)")

        try:
            # Get task from database
            task = Task.get(Task.id == task_id)
            logger.debug(f"Task {task_id} retrieved from database")

            # Create agent instance
            agent = ArxivAnalysisAgent()
            logger.debug("ArxivAnalysisAgent instance created")

            # Process the task
            logger.info(f"🔄 Processing task {task_id} of type {task_type}")
            result = await agent.process_task(task)
            logger.info(f"✅ Task {task_id} processed successfully")

            # Mark task as completed
            task.status = "completed"
            task.result = result
            task.save()
            logger.debug(f"Task {task_id} marked as completed")

            # Publish task completion event
            task_events.task_completed(task_id=task_id, result=result)
            logger.debug(f"Task completion event published for task {task_id}")

        except DoesNotExist:
            logger.error(f"Task {task_id} not found in database")
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
            # Mark task as failed
            try:
                task = Task.get(Task.id == task_id)
                task.status = "failed"
                task.result = str(e)
                task.save()
            except Exception as e:
                logger.error(f"Error marking task {task_id} as failed: {e}")
                pass

        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error in handle_task_creation: {e}")
        # Don't close connection in exception handler either


async def check_and_process_pending_tasks(agent: ArxivAnalysisAgent):
    """Check for unprocessed tasks and process them"""
    try:
        # Check if database is already connected
        if hasattr(db, "is_closed") and db.is_closed():
            db.connect()

        # Get all pending tasks
        pending_tasks = Task.select().where(Task.status == "pending")
        task_count = pending_tasks.count()

        if task_count > 0:
            logger.info(f"🔍 Found {task_count} unprocessed tasks, processing...")

            for task in pending_tasks:
                try:
                    logger.info(
                        f"🔄 Processing missed task {task.id} of type {task.task_type}"
                    )

                    # Process the task
                    result = await agent.process_task(task)

                    # Mark as completed
                    task.status = "completed"
                    task.result = result
                    task.save()

                    # Notify completion
                    task_events.task_completed(task_id=task.id, result=result)

                    logger.info(f"✅ Missed task {task.id} successfully processed")

                except Exception as e:
                    logger.error(f"Error processing missed task {task.id}: {e}")
                    task.status = "failed"
                    task.result = str(e)
                    task.save()

        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error checking unprocessed tasks: {e}")
        # Don't close connection in exception handler either


async def periodic_monitoring(agent: ArxivAnalysisAgent):
    """Periodic monitoring of active research topics"""
    try:
        # Check if database is already connected
        if hasattr(db, "is_closed") and db.is_closed():
            db.connect()
        logger.debug("Database connection established (periodic_monitoring)")

        # Get all active topics
        active_topics = ResearchTopic.select().where(ResearchTopic.is_active)
        topic_count = active_topics.count()
        logger.debug(f"Found {topic_count} active research topics for monitoring")

        agent.update_status(
            "periodic_monitoring",
            f"Periodic monitoring of {topic_count} active topics",
        )

        for topic in active_topics:
            try:
                # Check if monitoring is enabled for user
                try:
                    settings = UserSettings.get(UserSettings.user_id == topic.user_id)
                    logger.debug(f"UserSettings for user {topic.user_id} retrieved")
                    if not settings.monitoring_enabled:
                        logger.debug(f"Monitoring disabled for user {topic.user_id}")
                        continue
                except DoesNotExist:
                    logger.debug(
                        f"UserSettings for user {topic.user_id} not found, skipping"
                    )
                    continue

                # Check when this topic was last monitored
                user_monitoring = agent.monitoring_active.get(topic.user_id)
                if user_monitoring:
                    last_check = user_monitoring.get(
                        "last_check", datetime.now() - timedelta(hours=1)
                    )
                    if datetime.now() - last_check < timedelta(minutes=30):
                        logger.debug(
                            f"Topic {topic.id} for user {topic.user_id} was recently checked, skipping"
                        )
                        continue  # Too early for re-check

                logger.info(
                    f"Periodic monitoring of topic {topic.id} for user {topic.user_id}"
                )

                # Perform search for new articles
                await agent.perform_arxiv_search(
                    topic.user_id, topic.target_topic, topic.search_area, topic.id
                )
                logger.debug(f"Search for new articles completed for topic {topic.id}")

                # Update last check time
                if topic.user_id in agent.monitoring_active:
                    agent.monitoring_active[topic.user_id]["last_check"] = (
                        datetime.now()
                    )
                    logger.debug(f"Last check time updated for user {topic.user_id}")

            except Exception as e:
                logger.error(f"Error monitoring topic {topic.id}: {e}")
                # Continue with next topic instead of stopping
                continue

        # Don't close connection here - let the caller manage it
        logger.debug("Database connection maintained (periodic_monitoring)")

    except Exception as e:
        logger.error(f"Error in periodic monitoring: {e}")
        # Don't close connection in exception handler either


async def main():
    """Main loop of arXiv analysis agent"""
    logger.info("Starting arXiv analysis agent...")

    init_db()
    logger.debug("Database initialization completed")
    agent = ArxivAnalysisAgent()
    logger.debug("ArxivAnalysisAgent initialized")

    # Set initial status
    agent.update_status("starting", "Starting arXiv analysis agent")

    # Subscribe to events for new tasks
    event_bus = get_event_bus()
    logger.debug("Event bus instance obtained")
    task_events.subscribe_to_creations(handle_task_creation)
    logger.debug("Subscription to task creation events completed")

    # Start event processing in background
    asyncio.create_task(event_bus.start_processing(poll_interval=0.5))
    logger.debug("Background event processing started")

    # Main loop - periodic monitoring of active topics
    agent.update_status("running", "Agent is running and ready to work")

    while True:
        try:
            logger.debug("Starting main agent loop iteration")
            agent.update_status("checking_tasks", "Checking unprocessed tasks")

            # Check unprocessed tasks
            await check_and_process_pending_tasks(agent)

            # Perform periodic monitoring of active topics
            await periodic_monitoring(agent)

            agent.update_status("idle", "Waiting for next monitoring cycle (5 minutes)")
            logger.debug("Main loop iteration completed, sleeping for 5 minutes")
            await asyncio.sleep(300)  # Check every 5 minutes

        except Exception as e:
            logger.error(f"Error in main agent loop: {e}")
            # Don't exit the main loop on errors, just wait and continue
            await asyncio.sleep(60)  # Wait a minute before retrying


if __name__ == "__main__":
    try:
        logger.info("AI agent starting as main process")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("AI agent stopped by user")
    except Exception as e:
        logger.error(f"Critical AI agent error: {e}")
        raise
