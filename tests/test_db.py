"""Тесты SQLite-слоя."""

from __future__ import annotations

from app import db
from app.config import Settings


async def test_save_load_and_clear(settings: Settings) -> None:
    await db.init_db(settings.db_path)
    await db.save_exchange(settings.db_path, 1, "Вопрос", "Ответ", ["Тезис 1", "Тезис 2"], 4, 2)

    assert await db.load_history(settings.db_path, 1, 4) == [
        {"role": "user", "content": "Вопрос"},
        {"role": "assistant", "content": "Ответ"},
    ]
    assert await db.load_theses(settings.db_path, 1, 2) == ["Тезис 1", "Тезис 2"]
    assert await db.all_user_ids(settings.db_path) == [1]

    await db.clear(settings.db_path, 1)
    assert await db.load_theses(settings.db_path, 1, 2) == []
    assert await db.load_history(settings.db_path, 1, 4) == []
    assert await db.all_user_ids(settings.db_path) == []


async def test_old_records_are_trimmed(settings: Settings) -> None:
    await db.init_db(settings.db_path)
    for index in range(5):
        await db.save_exchange(
            settings.db_path,
            1,
            f"Q{index}",
            f"A{index}",
            [f"T{index}"],
            history_limit=4,
            thesis_limit=2,
        )

    history = await db.load_history(settings.db_path, 1, 10)
    assert [item["content"] for item in history] == ["Q3", "A3", "Q4", "A4"]
    assert await db.load_theses(settings.db_path, 1, 10) == ["T3", "T4"]
