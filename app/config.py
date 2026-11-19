"""Настройки и системные промпты для обоих режимов бота."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = (
    "Ты полезный AI-ассистент. Отвечай по делу. "
    "В конце каждого ответа выдели основные тезисы диалога в виде списка "
    "ключевых моментов для сохранения их в базу данных. "
    "Тезисы должны быть выделены в виде 'Пользователь хочет поехать в [место]', "
    "'Пользователь хочет купить [товар]', 'Саша хочет узнатть [информация]' и т.д."
)

DOMAIN_INSTRUCTION = (
    "Ты консультант по услугам страхования: страхование жизни, накопления, "
    "пенсионные программы и страхование сотрудников. Отвечай на языке пользователя, "
    "кратко и по делу. Не выдумывай цены, сроки и условия компании. "
    "Если данных недостаточно, предложи уточнить детали или обратиться к специалисту."
)

JSON_FORMAT_INSTRUCTION = (
    "Верни ровно один JSON-объект с двумя ключами в таком порядке: "
    "'тезисы' — массив строк с ключевыми моментами текущего обмена "
    "(вопрос пользователя и твой ответ), "
    "'message' — строка с ответом, который увидит пользователь. "
    "Тезисы в чат не отправляются, формулируй их коротко "
    "(например: 'Пользователь хочет застраховать Life')."
)


@dataclass(frozen=True, slots=True)
class Settings:
    """Все параметры, необходимые для запуска бота."""

    bot_token: str
    telegram_proxy: str | None
    openai_api_key: str
    openai_base_url: str | None
    openai_model: str
    db_path: Path
    memory_pairs: int
    thesis_limit: int
    log_level: str
    log_file: Path | None


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _positive_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} должно быть целым числом") from exc
    if value <= 0:
        raise SystemExit(f"{name} должно быть больше нуля")
    return value


def load_settings() -> Settings:
    """Прочитать переменные окружения и проверить обязательные из них."""
    bot_token = _env("BOT_TOKEN")
    api_key = _env("OPENAI_API_KEY") or _env("PROXYAPI_API_KEY")
    base_url = _env("OPENAI_BASE_URL") or _env("PROXYAPI_BASE_URL") or None
    model = _env("OPENAI_MODEL") or _env("CHAT_MODEL") or "gpt-4o-mini"

    if not bot_token:
        raise SystemExit("Не задан BOT_TOKEN — см. .env.example")
    if not api_key:
        raise SystemExit("Не задан OPENAI_API_KEY (или PROXYAPI_API_KEY) — см. .env.example")

    log_file = _env("LOG_FILE")
    return Settings(
        bot_token=bot_token,
        telegram_proxy=_env("TELEGRAM_PROXY") or None,
        openai_api_key=api_key,
        openai_base_url=base_url,
        openai_model=model,
        db_path=Path(_env("DB_PATH") or "data/consultant.db"),
        memory_pairs=_positive_int("MEMORY_PAIRS", 10),
        thesis_limit=_positive_int("THESIS_LIMIT", 30),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        log_file=Path(log_file) if log_file else None,
    )
