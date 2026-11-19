"""Тесты короткой и длинной памяти."""

from __future__ import annotations

from app.config import Settings
from app.memory import LongMemory, ShortMemory


async def test_short_memory_keeps_last_pairs_only(settings: Settings) -> None:
    memory = ShortMemory(settings.memory_pairs)
    for index in range(4):
        await memory.save_exchange(1, f"Q{index}", f"A{index}", [f"T{index}"])

    history = await memory.get_history(1)
    assert [item["content"] for item in history] == ["Q2", "A2", "Q3", "A3"]
    assert memory.load_theses(1) == []

    await memory.clear(1)
    assert await memory.get_history(1) == []


async def test_long_memory_survives_restart_and_reset(settings: Settings) -> None:
    memory = LongMemory(settings)
    await memory.initialize()
    await memory.save_exchange(7, "Вопрос", "Ответ", ["Саша хочет узнать условия"])

    restarted = LongMemory(settings)
    await restarted.initialize()
    assert restarted.load_theses(7) == ["Саша хочет узнать условия"]
    assert [item["content"] for item in await restarted.get_history(7)] == [
        "Вопрос",
        "Ответ",
    ]

    await restarted.clear(7)
    assert restarted.load_theses(7) == []

    fresh = LongMemory(settings)
    await fresh.initialize()
    assert fresh.load_theses(7) == []
