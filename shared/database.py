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
    DoesNotExist,
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
    """Исследовательские темы для анализа arXiv"""
    id = AutoField()
    user_id = BigIntegerField()
    target_topic = TextField()  # Целевая тема (что ищем)
    search_area = TextField()   # Область поиска (где ищем)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class ArxivPaper(BaseModel):
    """Статьи с arXiv"""
    id = AutoField()
    arxiv_id = CharField(max_length=50, unique=True)
    title = TextField()
    authors = TextField()  # JSON строка с авторами
    summary = TextField()
    categories = TextField()  # JSON строка с категориями
    published = DateTimeField()
    updated = DateTimeField()
    pdf_url = TextField()
    abs_url = TextField()
    journal_ref = TextField(null=True)
    doi = TextField(null=True)
    comment = TextField(null=True)
    primary_category = CharField(max_length=50, null=True)
    full_text = TextField(null=True)  # Полный текст если удалось извлечь
    created_at = DateTimeField(default=datetime.now)


class PaperAnalysis(BaseModel):
    """Анализ соответствия статьи исследовательским темам"""
    id = AutoField()
    paper = ForeignKeyField(ArxivPaper, backref="analyses")
    topic = ForeignKeyField(ResearchTopic, backref="analyses")
    
    # Оценки релевантности (0-100%)
    search_area_relevance = FloatField()    # Соответствие области поиска
    target_topic_relevance = FloatField()   # Присутствие целевой темы
    overall_relevance = FloatField()        # Интегральная оценка
    
    # Ключевые фрагменты и обоснования
    key_fragments = TextField(null=True)    # JSON с цитатами
    contextual_reasoning = TextField(null=True)  # Обоснование пересечения тем
    
    # Краткое резюме
    summary = TextField(null=True)
    innovation_assessment = TextField(null=True)  # Оценка инновационности
    practical_significance = TextField(null=True)  # Практическая значимость
    
    status = CharField(max_length=20, default="pending")  # pending, analyzed, sent
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class UserSettings(BaseModel):
    """Настройки пользователя для фильтрации и анализа"""
    id = AutoField()
    user_id = BigIntegerField(unique=True)
    
    # Пороги релевантности
    min_search_area_relevance = FloatField(default=50.0)    # Минимум для области поиска
    min_target_topic_relevance = FloatField(default=50.0)   # Минимум для целевой темы
    min_overall_relevance = FloatField(default=60.0)        # Минимум общей релевантности
    
    # Настройки уведомлений
    instant_notification_threshold = FloatField(default=80.0)  # Мгновенные уведомления
    daily_digest_threshold = FloatField(default=50.0)          # Дневная сводка
    weekly_digest_threshold = FloatField(default=30.0)         # Недельный дайджест
    
    # Фильтры времени
    days_back_to_search = CharField(max_length=10, default="7")  # Глубина поиска в днях
    excluded_categories = TextField(null=True)  # JSON с исключенными категориями arXiv
    
    # Состояние мониторинга
    monitoring_enabled = BooleanField(default=True)
    
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


def init_db():
    db.connect()
    db.create_tables([
        Message, 
        Task, 
        ResearchTopic, 
        ArxivPaper, 
        PaperAnalysis, 
        UserSettings
    ], safe=True)
    db.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
