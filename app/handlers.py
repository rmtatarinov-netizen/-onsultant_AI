"""Обработчики команд и сообщений общего для обоих ботов роутера."""

from __future__ import annotations

import json
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from openai import AsyncOpenAI

from .config import Settings
from .llm import ask_model, build_messages
from .logging_config import get_theses_logger
from .memory import LongMemory, ShortMemory

logger = logging.getLogger(__name__)
router = Router()
SEND_CHUNK = 4000


def split_text(text: str, limit: int = SEND_CHUNK) -> list[str]:
    """Разбить ответ на части, укладывающиеся в лимит Telegram."""
    parts: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip(" \n")
    if text:
        parts.append(text)
    return parts


@router.message(CommandStart())
async def cmd_start(message: Message, settings: Settings, mode: str) -> None:
    """Приветствие с пояснением особенностей режима."""
    lines = [
        "Здравствуйте! Я AI-консультант по услугам страхования:",
        "жизнь, накопления, пенсия и страхование сотрудников.",
        "",
    ]
    if mode == "long":
        lines.append("Я восстанавливаю важные детали прошлых разговоров из базы данных.")
    else:
        lines.append(
            f"В этом режиме я помню только последние {settings.memory_pairs} "
            "пар сообщений в текущем сеансе."
        )
    lines += ["", "Команды: /help — справка, /memory — о памяти, /reset — очистить память."]
    await message.answer("\n".join(lines))


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Краткая справка."""
    await message.answer(
        "Напишите вопрос по страхованию — я отвечу и сохраню ключевые моменты. "
        "Тезисы уходят только в логи сервера, в чат приходит сам ответ. "
        "Команды: /memory, /reset."
    )


@router.message(Command("memory"))
async def cmd_memory(
    message: Message,
    memory: ShortMemory | LongMemory,
    mode: str,
) -> None:
    """Показать, сколько тезисов сохранено в текущем режиме."""
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return
    saved = len(memory.load_theses(message.from_user.id))
    await message.answer(
        f"Режим: {mode}. Сохранено тезисов: {saved}. Тезисы видны только в консоли сервера."
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message, memory: ShortMemory | LongMemory) -> None:
    """Принудительно очистить контекст пользователя."""
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return
    user_id = message.from_user.id
    async with memory.get_lock(user_id):
        await memory.clear(user_id)
    logger.info("Память принудительно очищена для user_id=%s", user_id)
    await message.answer("Контекст очищен. Начнём диалог заново!")


@router.message(F.text)
async def handle_text(
    message: Message,
    settings: Settings,
    memory: ShortMemory | LongMemory,
    mode: str,
    openai_client: AsyncOpenAI,
) -> None:
    """Основной сценарий: вопрос -> JSON от модели -> ответ в чат, тезисы в лог."""
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя.")
        return

    user_id = message.from_user.id
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пришлите, пожалуйста, текстовый вопрос.")
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    async with memory.get_lock(user_id):
        messages = build_messages(
            settings,
            memory.load_theses(user_id),
            await memory.get_history(user_id),
            text,
        )
        try:
            reply = await ask_model(openai_client, settings, messages)
        except Exception:
            logger.exception("Ошибка при обращении к модели, user_id=%s", user_id)
            await message.answer("Не удалось получить ответ. Попробуйте ещё раз позже.")
            return

        get_theses_logger().info(
            "user_id=%s mode=%s тезисы: %s",
            user_id,
            mode,
            json.dumps(reply.theses, ensure_ascii=False),
        )
        await memory.save_exchange(user_id, text, reply.message, reply.theses)

    for chunk in split_text(reply.message):
        await message.answer(chunk)


@router.message()
async def handle_other(message: Message) -> None:
    """Заглушка для нетекстовых сообщений."""
    await message.answer("Пока я работаю только с текстовыми сообщениями.")
