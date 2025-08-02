import os
from peewee import (  # type: ignore
    SqliteDatabase,
    Model,
    AutoField,
    BigIntegerField,
    TextField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    FloatField,
    BooleanField,
)
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "database.db")
db = SqliteDatabase(DATABASE_PATH)


class BaseModel(Model):
    class Meta:
        database = db


class Message(BaseModel):
    id = AutoField()
    user_id = BigIntegerField()
    content = TextField()
    message_type = CharField(max_length=50, default="user")  # user, ai_response
    status = CharField(
        max_length=20, default="pending"
    )  # pending, processing, completed
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class Task(BaseModel):
    id = AutoField()
    message_id = ForeignKeyField(Message, backref="tasks", null=True)
    task_type = CharField(max_length=50)
    data = TextField()
    status = CharField(
        max_length=20, default="pending"
    )  # pending, processing, completed, failed
    result = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class ResearchTopic(BaseModel):
    """Research topics for arXiv analysis"""

    id = AutoField()
    user_id = BigIntegerField()
    target_topic = TextField()  # Target topic (what we're looking for)
    search_area = TextField()  # Search area (where we're looking)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class ArxivPaper(BaseModel):
    """Articles from arXiv"""

    id = AutoField()
    arxiv_id = CharField(max_length=50, unique=True)
    title = TextField()
    authors = TextField()  # JSON string with authors
    summary = TextField()
    categories = TextField()  # JSON string with categories
    published = DateTimeField()
    updated = DateTimeField()
    pdf_url = TextField()
    abs_url = TextField()
    journal_ref = TextField(null=True)
    doi = TextField(null=True)
    comment = TextField(null=True)
    primary_category = CharField(max_length=50, null=True)
    full_text = TextField(null=True)  # Full text if successfully extracted
    created_at = DateTimeField(default=datetime.now)


class PaperAnalysis(BaseModel):
    """Analysis of article relevance to research topics"""

    id = AutoField()
    paper = ForeignKeyField(ArxivPaper, backref="analyses")
    topic = ForeignKeyField(ResearchTopic, backref="analyses")

    # Relevance scores (0-100%)
    search_area_relevance = FloatField()  # Search area relevance
    target_topic_relevance = FloatField()  # Target topic presence
    overall_relevance = FloatField()  # Overall score

    # Key fragments and reasoning
    key_fragments = TextField(null=True)  # JSON with quotes
    contextual_reasoning = TextField(null=True)  # Topic intersection reasoning

    # Brief summary
    summary = TextField(null=True)
    innovation_assessment = TextField(null=True)  # Innovation assessment
    practical_significance = TextField(null=True)  # Practical significance

    status = CharField(max_length=20, default="pending")  # pending, analyzed, sent
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class UserSettings(BaseModel):
    """User settings for filtering and analysis"""

    id = AutoField()
    user_id = BigIntegerField(unique=True)

    # Relevance thresholds
    min_search_area_relevance = FloatField(default=50.0)  # Minimum for search area
    min_target_topic_relevance = FloatField(default=50.0)  # Minimum for target topic
    min_overall_relevance = FloatField(default=60.0)  # Minimum overall relevance

    # Notification settings
    instant_notification_threshold = FloatField(default=80.0)  # Instant notifications
    daily_digest_threshold = FloatField(default=50.0)  # Daily digest
    weekly_digest_threshold = FloatField(default=30.0)  # Weekly digest

    # Time filters
    days_back_to_search = CharField(max_length=10, default="7")  # Search depth in days
    excluded_categories = TextField(null=True)  # JSON with excluded arXiv categories

    # Monitoring status
    monitoring_enabled = BooleanField(default=True)

    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class AgentStatus(BaseModel):
    """Real-time agent status tracking"""

    id = AutoField()
    agent_id = CharField(max_length=50, default="main_agent")  # Agent identifier
    status = CharField(max_length=50)  # Current status
    activity = TextField()  # Current activity description
    current_user_id = BigIntegerField(null=True)  # User being processed
    current_topic_id = BigIntegerField(null=True)  # Topic being processed
    papers_processed = BigIntegerField(default=0)  # Papers processed in current session
    papers_found = BigIntegerField(default=0)  # Relevant papers found
    last_activity = DateTimeField(default=datetime.now)
    session_start = DateTimeField(default=datetime.now)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


def init_db():
    db.connect()
    db.create_tables(
        [
            Message,
            Task,
            ResearchTopic,
            ArxivPaper,
            PaperAnalysis,
            UserSettings,
            AgentStatus,
        ],
        safe=True,
    )
    db.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
