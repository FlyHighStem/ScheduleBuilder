import json
import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent.parent / "schedulebuilder.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection



def ensure_column(connection, table_name, column_name, column_definition):
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")

def initialize_database():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                settings_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'school',
                urgency TEXT NOT NULL DEFAULT 'none',
                importance TEXT NOT NULL DEFAULT 'medium',
                due TEXT NOT NULL DEFAULT '',
                day_offset INTEGER NOT NULL DEFAULT 0,
                start_hour INTEGER NOT NULL DEFAULT 9,
                end_hour INTEGER NOT NULL DEFAULT 10,
                payload_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY(user_email) REFERENCES users(email)
            )
            """
        )
        ensure_column(connection, "users", "name", "TEXT NOT NULL DEFAULT 'Test User'")
        ensure_column(connection, "users", "settings_json", "TEXT NOT NULL DEFAULT '{}'")
        ensure_column(connection, "tasks", "user_email", "TEXT NOT NULL DEFAULT 'test@test.com'")
        ensure_column(connection, "tasks", "name", "TEXT NOT NULL DEFAULT 'Untitled Task'")
        ensure_column(connection, "tasks", "description", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "tasks", "category", "TEXT NOT NULL DEFAULT 'school'")
        ensure_column(connection, "tasks", "urgency", "TEXT NOT NULL DEFAULT 'none'")
        ensure_column(connection, "tasks", "importance", "TEXT NOT NULL DEFAULT 'medium'")
        ensure_column(connection, "tasks", "due", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "tasks", "day_offset", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(connection, "tasks", "start_hour", "INTEGER NOT NULL DEFAULT 9")
        ensure_column(connection, "tasks", "end_hour", "INTEGER NOT NULL DEFAULT 10")
        ensure_column(connection, "tasks", "payload_json", "TEXT NOT NULL DEFAULT '{}'")

        connection.execute(
            """
            INSERT OR IGNORE INTO users (email, name, settings_json)
            VALUES (?, ?, ?)
            """,
            ("test@test.com", "Test User", json.dumps({"theme": "dark", "reminders": True}))
        )


def task_from_row(row):
    payload = json.loads(row["payload_json"] or "{}")
    payload.update({
        "id": row["id"],
        "name": row["name"],
        "title": row["name"],
        "description": row["description"],
        "category": row["category"],
        "urgency": row["urgency"],
        "importance": row["importance"],
        "due": row["due"],
        "dayOffset": row["day_offset"],
        "hour": row["start_hour"],
        "startHour": row["start_hour"],
        "endHour": row["end_hour"],
    })
    return payload


class TaskRepository:
    def list_for_user(self, user_email):
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks WHERE user_email = ? ORDER BY due, start_hour, name",
                (user_email,)
            ).fetchall()
        return [task_from_row(row) for row in rows]

    def upsert(self, user_email, task):
        task_id = str(task["id"])
        name = task.get("name") or task.get("title") or "Untitled Task"
        start_hour = int(task.get("startHour", task.get("hour", 9)) or 9)
        end_hour = int(task.get("endHour", start_hour + 1) or start_hour + 1)
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                    id, user_email, name, description, category, urgency, importance,
                    due, day_offset, start_hour, end_hour, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    category = excluded.category,
                    urgency = excluded.urgency,
                    importance = excluded.importance,
                    due = excluded.due,
                    day_offset = excluded.day_offset,
                    start_hour = excluded.start_hour,
                    end_hour = excluded.end_hour,
                    payload_json = excluded.payload_json
                """,
                (
                    task_id,
                    user_email,
                    name,
                    task.get("description", ""),
                    task.get("category", "school"),
                    task.get("urgency", "none"),
                    task.get("importance", "medium"),
                    task.get("due", ""),
                    int(task.get("dayOffset", 0) or 0),
                    start_hour,
                    end_hour,
                    json.dumps(task),
                )
            )
        return task

    def delete(self, user_email, task_id):
        with get_connection() as connection:
            connection.execute(
                "DELETE FROM tasks WHERE user_email = ? AND id = ?",
                (user_email, str(task_id))
            )

    def clear(self, user_email):
        with get_connection() as connection:
            connection.execute("DELETE FROM tasks WHERE user_email = ?", (user_email,))


class UserRepository:
    def upsert(self, email, name, settings=None):
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (email, name, settings_json) VALUES (?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    name = excluded.name,
                    settings_json = excluded.settings_json
                """,
                (email, name, json.dumps(settings or {}))
            )
