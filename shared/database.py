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


def init_db():
    db.connect()
    db.create_tables([Message, Task], safe=True)
    db.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
