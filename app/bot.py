"""Точка входа: создаёт бота с выбранным режимом памяти."""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from openai import AsyncOpenAI

from .config import Settings, load_settings
from .handlers import router
from .logging_config import setup_logging
from .memory import LongMemory, ShortMemory

logger = logging.getLogger(__name__)


async def run_bot(settings: Settings, mode: Literal["short", "long"]) -> None:
    """Настроить зависимости и запустить long polling."""
    setup_logging(settings.log_level, settings.log_file)

    memory: ShortMemory | LongMemory
    if mode == "long":
        long_memory = LongMemory(settings)
        await long_memory.initialize()
        memory = long_memory
    else:
        memory = ShortMemory(settings.memory_pairs)
        logger.info("Короткая память: последние %s сообщений в RAM", settings.memory_pairs * 2)

    session = AiohttpSession(proxy=settings.telegram_proxy) if settings.telegram_proxy else None
    bot = Bot(token=settings.bot_token, session=session)
    client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    dp = Dispatcher()
    dp.include_router(router)
    dp["settings"] = settings
    dp["memory"] = memory
    dp["mode"] = mode
    dp["openai_client"] = client

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Бот (%s) запущен. Модель: %s", mode, settings.openai_model)
        await dp.start_polling(bot)
    except TelegramNetworkError as exc:
        logger.error("Нет связи с api.telegram.org: %s", exc)
        raise SystemExit(1) from exc
    finally:
        await client.close()
        await bot.session.close()


def main(mode: Literal["short", "long"]) -> None:
    """Прочитать настройки и запустить бота до прерывания."""
    settings = load_settings()
    try:
        asyncio.run(run_bot(settings, mode))
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
