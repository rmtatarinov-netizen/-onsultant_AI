"""Реализации короткой (RAM) и длинной (SQLite) памяти бота."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from typing import Protocol

from . import db
from .config import Settings

logger = logging.getLogger(__name__)


class Memory(Protocol):
    """Общий интерфейс обоих режимов памяти."""

    async def initialize(self) -> None: ...

    def get_lock(self, user_id: int) -> asyncio.Lock: ...

    async def get_history(self, user_id: int) -> list[dict[str, str]]: ...

    def load_theses(self, user_id: int) -> list[str]: ...

    async def save_exchange(
        self, user_id: int, question: str, answer: str, theses: list[str]
    ) -> None: ...

    async def clear(self, user_id: int) -> None: ...


class ShortMemory:
    """Последние N пар сообщений в оперативной памяти, без долгосрочных тезисов."""

    def __init__(self, memory_pairs: int) -> None:
        self._limit = memory_pairs * 2
        self._history: dict[int, deque[dict[str, str]]] = defaultdict(
            lambda: deque(maxlen=self._limit)
        )
        self._locks: dict[int, asyncio.Lock] = {}

    async def initialize(self) -> None:
        return None

    def get_lock(self, user_id: int) -> asyncio.Lock:
        return self._locks.setdefault(user_id, asyncio.Lock())

    async def get_history(self, user_id: int) -> list[dict[str, str]]:
        return list(self._history[user_id])

    def load_theses(self, user_id: int) -> list[str]:
        return []

    async def save_exchange(
        self, user_id: int, question: str, answer: str, theses: list[str]
    ) -> None:
        self._history[user_id].append({"role": "user", "content": question})
        self._history[user_id].append({"role": "assistant", "content": answer})

    async def clear(self, user_id: int) -> None:
        self._history.pop(user_id, None)


class LongMemory:
    """История и тезисы в SQLite; тезисы подставляются в системный промпт."""

    def __init__(self, settings: Settings) -> None:
        self._db_path = settings.db_path
        self._history_limit = settings.memory_pairs * 2
        self._thesis_limit = settings.thesis_limit
        self._theses: dict[int, list[str]] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    async def initialize(self) -> None:
        await db.init_db(self._db_path)
        for user_id in await db.all_user_ids(self._db_path):
            self._theses[user_id] = await db.load_theses(self._db_path, user_id, self._thesis_limit)
        total = sum(len(items) for items in self._theses.values())
        logger.info("Восстановлено тезисов из SQLite: %s", total)

    def get_lock(self, user_id: int) -> asyncio.Lock:
        return self._locks.setdefault(user_id, asyncio.Lock())

    async def get_history(self, user_id: int) -> list[dict[str, str]]:
        return await db.load_history(self._db_path, user_id, self._history_limit)

    def load_theses(self, user_id: int) -> list[str]:
        return list(self._theses.get(user_id, []))

    async def save_exchange(
        self, user_id: int, question: str, answer: str, theses: list[str]
    ) -> None:
        await db.save_exchange(
            self._db_path,
            user_id,
            question,
            answer,
            theses,
            self._history_limit,
            self._thesis_limit,
        )
        current = self._theses.get(user_id, [])
        self._theses[user_id] = (current + theses)[-self._thesis_limit :]

    async def clear(self, user_id: int) -> None:
        await db.clear(self._db_path, user_id)
        self._theses.pop(user_id, None)
