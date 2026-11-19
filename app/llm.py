"""Запрос к OpenAI-совместимому API и разбор структурированного ответа."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from openai import AsyncOpenAI

from .config import DOMAIN_INSTRUCTION, JSON_FORMAT_INSTRUCTION, SYSTEM_PROMPT, Settings

logger = logging.getLogger(__name__)

RESPONSE_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "json_schema": {
        "name": "consultant_reply",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "тезисы": {"type": "array", "items": {"type": "string"}},
                "message": {"type": "string"},
            },
            "required": ["тезисы", "message"],
            "additionalProperties": False,
        },
    },
}


@dataclass(frozen=True, slots=True)
class Reply:
    """Ответ модели: тезисы для логов и сообщение для пользователя."""

    theses: list[str]
    message: str


def build_messages(
    settings: Settings,
    saved_theses: list[str],
    history: list[dict[str, str]],
    user_text: str,
) -> list[dict[str, str]]:
    """Собрать сообщения: промпты, сохранённый контекст, история, вопрос."""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": DOMAIN_INSTRUCTION},
        {"role": "system", "content": JSON_FORMAT_INSTRUCTION},
    ]
    if saved_theses:
        lines = "\n".join(f"- {thesis}" for thesis in saved_theses)
        messages.append(
            {
                "role": "system",
                "content": "Сохранённые тезисы из предыдущих диалогов:\n" + lines,
            }
        )
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages


def parse_reply(content: str) -> Reply:
    """Проверить JSON от модели и вернуть тезисы и сообщение."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Ответ модели не является корректным JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("Ответ модели должен быть объектом JSON")

    theses = payload.get("тезисы")
    message = payload.get("message")
    if not isinstance(theses, list) or not all(
        isinstance(item, str) and item.strip() for item in theses
    ):
        raise ValueError("Ключ 'тезисы' должен быть массивом непустых строк")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Ключ 'message' должен быть непустой строкой")

    keys = list(payload)[:2]
    if keys != ["тезисы", "message"]:
        logger.warning("Порядок ключей в JSON отличается от ожидаемого: %s", keys)

    return Reply(
        theses=[item.strip() for item in theses],
        message=message.strip(),
    )


async def ask_model(
    client: AsyncOpenAI,
    settings: Settings,
    messages: list[dict[str, str]],
) -> Reply:
    """Получить от модели JSON с двумя ключами, при ошибке — fallback на текст."""
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=0.3,
        response_format=RESPONSE_FORMAT,
    )
    content = response.choices[0].message.content or ""
    try:
        return parse_reply(content)
    except (ValueError, TypeError) as exc:
        logger.warning("Некорректный ответ модели (%s), используется fallback", exc)
        return Reply(theses=[], message=content.strip() or "Не удалось сформировать ответ.")
