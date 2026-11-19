"""Тесты структурированного ответа модели."""

from __future__ import annotations

import json

import pytest
from conftest import FakeClient

from app.config import Settings
from app.llm import RESPONSE_FORMAT, ask_model, build_messages, parse_reply


def test_response_format_has_two_keys_in_order() -> None:
    schema = RESPONSE_FORMAT["json_schema"]
    assert schema["strict"] is True
    assert list(schema["schema"]["properties"]) == ["тезисы", "message"]
    assert schema["schema"]["required"] == ["тезисы", "message"]
    assert schema["schema"]["additionalProperties"] is False


def test_build_messages_adds_saved_theses(settings: Settings) -> None:
    messages = build_messages(
        settings,
        ["Пользователь хочет пенсию"],
        [{"role": "user", "content": "старый вопрос"}],
        "новый вопрос",
    )
    assert [item["role"] for item in messages] == [
        "system",
        "system",
        "system",
        "system",
        "user",
        "user",
    ]
    assert "Пользователь хочет пенсию" in messages[3]["content"]
    assert messages[-1]["content"] == "новый вопрос"


def test_parse_reply_keeps_order_and_values() -> None:
    content = json.dumps({"тезисы": ["Т1", "Т2"], "message": "Ответ"}, ensure_ascii=False)
    reply = parse_reply(content)
    assert reply.theses == ["Т1", "Т2"]
    assert reply.message == "Ответ"


@pytest.mark.parametrize(
    "content",
    [
        "не json",
        "[]",
        '{"тезисы": "строка", "message": "Ответ"}',
        '{"тезисы": [], "message": ""}',
    ],
)
def test_parse_reply_rejects_invalid_payload(content: str) -> None:
    with pytest.raises(ValueError):
        parse_reply(content)


async def test_ask_model_uses_strict_schema(settings: Settings, reply_json: str) -> None:
    client = FakeClient(reply_json)
    reply = await ask_model(client, settings, [{"role": "user", "content": "вопрос"}])

    assert reply.message == "Ответ консультанта"
    assert reply.theses == ["Пользователь хочет застраховать жизнь"]
    assert client.completions.kwargs["response_format"] == RESPONSE_FORMAT
    assert client.completions.kwargs["temperature"] == 0.3


async def test_ask_model_falls_back_to_plain_text(settings: Settings) -> None:
    client = FakeClient("обычный текст ответа")
    reply = await ask_model(client, settings, [])

    assert reply.theses == []
    assert reply.message == "обычный текст ответа"
