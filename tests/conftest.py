"""Общие фикстуры и подставные объекты для тестов."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        bot_token="test-token",
        telegram_proxy=None,
        openai_api_key="test-key",
        openai_base_url=None,
        openai_model="gpt-4o-mini",
        db_path=tmp_path / "data" / "consultant.db",
        memory_pairs=2,
        thesis_limit=3,
        log_level="INFO",
        log_file=None,
    )


@pytest.fixture
def reply_json() -> str:
    return json.dumps(
        {
            "тезисы": ["Пользователь хочет застраховать жизнь"],
            "message": "Ответ консультанта",
        },
        ensure_ascii=False,
    )


class FakeCompletions:
    """Подставной объект client.chat.completions."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.kwargs = kwargs
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    """Подставной OpenAI-клиент."""

    def __init__(self, content: str) -> None:
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


class FakeMessage:
    """Подставное сообщение aiogram."""

    def __init__(self, text: str = "", user_id: int = 1, chat_id: int = 1) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        self.answers: list[str] = []
        self.actions: list[str] = []
        self.bot = SimpleNamespace(send_chat_action=self._send_action)

    async def answer(self, text: str) -> None:
        self.answers.append(text)

    async def _send_action(self, chat_id: int, action: str) -> None:
        self.actions.append(action)
