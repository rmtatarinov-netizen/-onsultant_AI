"""Тесты обработчиков: тезисы в логах, ответ в чате, сброс памяти."""

from __future__ import annotations

import logging

import pytest
from conftest import FakeClient, FakeMessage

from app import db
from app.config import Settings
from app.handlers import cmd_reset, handle_text, split_text
from app.memory import LongMemory, ShortMemory


async def test_handle_text_logs_theses_but_sends_only_message(
    settings: Settings, reply_json: str, caplog: pytest.LogCaptureFixture
) -> None:
    memory = ShortMemory(settings.memory_pairs)
    message = FakeMessage("Хочу застраховать жизнь")

    with caplog.at_level(logging.INFO, logger="theses"):
        await handle_text(message, settings, memory, "short", FakeClient(reply_json))

    assert message.answers == ["Ответ консультанта"]
    assert any(record.name == "theses" and "тезисы" in record.message for record in caplog.records)
    assert (await memory.get_history(1))[0]["content"] == "Хочу застраховать жизнь"


async def test_long_mode_injects_theses_into_prompt(settings: Settings, reply_json: str) -> None:
    memory = LongMemory(settings)
    await memory.initialize()
    await memory.save_exchange(1, "старый вопрос", "старый ответ", ["Пользователь хочет пенсию"])

    client = FakeClient(reply_json)
    message = FakeMessage("А что по накоплениям?")
    await handle_text(message, settings, memory, "long", client)

    sent = client.completions.kwargs["messages"]
    assert any("Пользователь хочет пенсию" in item["content"] for item in sent)
    saved = await db.load_theses(settings.db_path, 1, 10)
    assert saved[-1] == "Пользователь хочет застраховать жизнь"


async def test_reset_clears_long_memory(settings: Settings) -> None:
    memory = LongMemory(settings)
    await memory.initialize()
    await memory.save_exchange(1, "Q", "A", ["T"])

    await cmd_reset(FakeMessage("/reset"), memory)

    assert memory.load_theses(1) == []
    assert await db.load_theses(settings.db_path, 1, 10) == []


def test_split_text() -> None:
    assert split_text("one two three", limit=8) == ["one two", "three"]
