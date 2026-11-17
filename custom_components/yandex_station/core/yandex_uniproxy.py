"""Read Alice shopping-list card text via the assistant WebSocket.

Local glagol often acknowledges sendText without a card when streaming TTS is
on (AlexxIT/YandexStation#631). The notes RPC is a different store. This client
reuses the existing cookie session and asks the assistant for the same numbered
text the station used to return.
"""
from __future__ import annotations

import asyncio
import time
import uuid

from aiohttp import ClientSession, WSMsgType

# Public web-client key from alice.yandex.ru, not an account credential.
_WEB_CLIENT_KEY = "effd5a3f-fd42-4a18-83a1-61766a6d0924"


class AliceAssistant:
    def __init__(self, http: ClientSession):
        self.http = http
        self.ws = None
        self.device_id = uuid.uuid4().hex
        self.dialog_id = ""
        self.seq = 0

    async def close(self):
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def send(self, name: str, payload: dict) -> str:
        self.seq += 1
        message_id = uuid.uuid4().hex
        await self.ws.send_json(
            {
                "event": {
                    "header": {
                        "namespace": "Vins" if name == "TextInput" else "System",
                        "name": name,
                        "messageId": message_id,
                        "seqNumber": self.seq,
                    },
                    "payload": payload,
                }
            }
        )
        return message_id

    async def receive(self) -> tuple[dict, dict]:
        while True:
            msg = await self.ws.receive()
            if msg.type != WSMsgType.TEXT:
                if msg.type in (WSMsgType.CLOSED, WSMsgType.CLOSE, WSMsgType.ERROR):
                    raise RuntimeError("Alice assistant connection closed")
                continue
            directive = msg.json().get("directive") or {}
            header = directive.get("header") or {}
            payload = directive.get("payload") or {}
            if header.get("name") == "Ping":
                await self.ws.send_json(
                    {
                        "event": {
                            "header": {
                                "namespace": "System",
                                "name": "Pong",
                                "messageId": uuid.uuid4().hex,
                                "refMessageId": header["messageId"],
                            },
                            "payload": {},
                        }
                    }
                )
                continue
            return header, payload

    async def connect(self) -> None:
        self.ws = await self.http.ws_connect(
            "wss://uniproxy.alice.yandex.ru/uni.ws",
            origin="https://alice.yandex.ru",
            heartbeat=30,
        )
        await self.send(
            "SynchronizeState",
            {
                "auth_token": _WEB_CLIENT_KEY,
                "uuid": self.device_id,
                "vins": {
                    "application": {
                        "app_id": "ru.yandex.searchplugin",
                        "platform": "android",
                        "device_id": self.device_id,
                    }
                },
                "supported_features": [],
                "request": {"experiments": []},
                "speechkitVersion": "1.0",
            },
        )
        async with asyncio.timeout(20):
            while True:
                header, _payload = await self.receive()
                if header.get("name") == "SynchronizeStateResponse":
                    return

    async def ask(self, text: str) -> str:
        message_id = await self.send(
            "TextInput",
            {
                "application": {
                    "app_id": "ru.yandex.searchplugin",
                    "app_version": "unknown",
                    "platform": "android",
                    "uuid": self.device_id,
                    "device_id": self.device_id,
                    "lang": "ru-RU",
                    "timezone": "Europe/Moscow",
                    "timestamp": str(int(time.time())),
                },
                "header": {"request_id": uuid.uuid4().hex, "dialog_id": self.dialog_id},
                "request": {
                    "event": {"type": "text_input", "text": text},
                    "voice_session": False,
                    "experiments": [],
                    "additional_options": {},
                    "environment_state": {"endpoints": []},
                },
                "topic": "general",
                "format": "audio/ogg;codecs=opus",
                "mime": "audio/ogg;codecs=opus",
                "punctuation": False,
            },
        )
        async with asyncio.timeout(25):
            while True:
                header, payload = await self.receive()
                if (
                    header.get("name") == "VinsResponse"
                    and header.get("refMessageId") == message_id
                ):
                    self.dialog_id = (payload.get("header") or {}).get(
                        "dialog_id", self.dialog_id
                    )
                    response = payload.get("response") or {}
                    card = response.get("card") or {}
                    text = card.get("text") or "\n".join(
                        c.get("text", "")
                        for c in response.get("cards") or []
                        if isinstance(c, dict)
                    )
                    if not isinstance(text, str) or not text.strip():
                        raise RuntimeError("Alice assistant returned no text")
                    return text


async def read_shopping_text(http: ClientSession) -> str:
    client = AliceAssistant(http)
    try:
        await client.connect()
        return await client.ask("Что в списке покупок")
    finally:
        await client.close()
