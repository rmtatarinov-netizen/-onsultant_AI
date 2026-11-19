"""Хранение истории диалогов и тезисов в SQLite."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS dialogue_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_user ON dialogue_messages (user_id, id);

CREATE TABLE IF NOT EXISTS theses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    thesis TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_theses_user ON theses (user_id, id);
"""


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_path, timeout=10)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _init_sync(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as connection:
        connection.executescript(SCHEMA)


def _save_exchange_sync(
    db_path: Path,
    user_id: int,
    question: str,
    answer: str,
    theses: list[str],
    history_limit: int,
    thesis_limit: int,
) -> None:
    with _connect(db_path) as connection:
        connection.executemany(
            "INSERT INTO dialogue_messages (user_id, role, content) VALUES (?, ?, ?)",
            [(user_id, "user", question), (user_id, "assistant", answer)],
        )
        if theses:
            connection.executemany(
                "INSERT INTO theses (user_id, thesis) VALUES (?, ?)",
                [(user_id, thesis) for thesis in theses],
            )
        connection.execute(
            """DELETE FROM dialogue_messages
               WHERE user_id = ? AND id NOT IN (
                   SELECT id FROM dialogue_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?
               )""",
            (user_id, user_id, history_limit),
        )
        connection.execute(
            """DELETE FROM theses
               WHERE user_id = ? AND id NOT IN (
                   SELECT id FROM theses WHERE user_id = ? ORDER BY id DESC LIMIT ?
               )""",
            (user_id, user_id, thesis_limit),
        )


def _load_theses_sync(db_path: Path, user_id: int, limit: int) -> list[str]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT thesis FROM theses WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [row[0] for row in reversed(rows)]


def _load_history_sync(db_path: Path, user_id: int, limit: int) -> list[dict[str, str]]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT role, content FROM dialogue_messages WHERE user_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]


def _clear_sync(db_path: Path, user_id: int) -> None:
    with _connect(db_path) as connection:
        connection.execute("DELETE FROM dialogue_messages WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM theses WHERE user_id = ?", (user_id,))


def _all_user_ids_sync(db_path: Path) -> list[int]:
    with _connect(db_path) as connection:
        rows = connection.execute("SELECT DISTINCT user_id FROM theses").fetchall()
    return [row[0] for row in rows]


async def init_db(db_path: Path) -> None:
    """Создать таблицы, если их ещё нет."""
    await asyncio.to_thread(_init_sync, db_path)


async def save_exchange(
    db_path: Path,
    user_id: int,
    question: str,
    answer: str,
    theses: list[str],
    history_limit: int,
    thesis_limit: int,
) -> None:
    """Сохранить пару вопрос/ответ и тезисы, обрезав старые записи."""
    await asyncio.to_thread(
        _save_exchange_sync,
        db_path,
        user_id,
        question,
        answer,
        theses,
        history_limit,
        thesis_limit,
    )


async def load_theses(db_path: Path, user_id: int, limit: int) -> list[str]:
    """Вернуть последние тезисы пользователя в хронологическом порядке."""
    return await asyncio.to_thread(_load_theses_sync, db_path, user_id, limit)


async def load_history(db_path: Path, user_id: int, limit: int) -> list[dict[str, str]]:
    """Вернуть последние сообщения пользователя в хронологическом порядке."""
    return await asyncio.to_thread(_load_history_sync, db_path, user_id, limit)


async def clear(db_path: Path, user_id: int) -> None:
    """Полностью удалить контекст пользователя из базы."""
    await asyncio.to_thread(_clear_sync, db_path, user_id)


async def all_user_ids(db_path: Path) -> list[int]:
    """Вернуть пользователей, у которых есть сохранённые тезисы."""
    return await asyncio.to_thread(_all_user_ids_sync, db_path)
