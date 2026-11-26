"""Клиент облачного диалога с Алисой.

Локальный glagol больше не отдаёт текст списка покупок: на «Что в списке
покупок» колонка присылает стриминговый ответ без `card.text`, поэтому синк
падал с `KeyError: 'text'`. Ходим в облачный диалог — тот же WebSocket, что у
приложения «Дом с Алисой»:

    wss://uniproxy.alice.yandex.net/uni.ws

Схема запроса: SynchronizeState -> пауза -> Vins.TextInput -> ответ, текст
лежит в `directive.payload.response.card(s).text`. Ответ приходит несколькими
кадрами (стриминг, InputStartAck, карточка), поэтому кадры фильтруются по
request_id.

Авторизация не своя: переиспользуем YandexSession (куки + x_token), так что
интеграция не заводит второй способ логина.

Идентичность клиента важна: `device_id` — серийник реальной колонки аккаунта
(quasar_info), `uuid` — случайный. На случайный device_id Яндекс отвечает
«Чтобы продолжить, вам необходимо авторизоваться в приложении Яндекс», на
веб-клиент (ru.yandex.webstandalone.desktop) — `ShoppingList: LR_NOT_ENABLED`.
"""

import asyncio
import json
import logging
import time
import uuid

from aiohttp import WSMsgType

from .yandex_session import YandexSession

_LOGGER = logging.getLogger(__package__)

UNIPROXY_URL = "wss://uniproxy.alice.yandex.net/uni.ws"

# приложение, которому Яндекс отдаёт навык списка покупок; веб-клиент получает
# LR_NOT_ENABLED, поэтому притворяемся мобильным приложением умного дома
APP_ID = "com.yandex.iot"
APP_VERSION = "26.18.0"
USER_AGENT = "com.yandex.iot/26.18.0 (Android 13)"
ORIGIN = "https://alice.yandex.ru"

# Алиса хранит фразу так, как её произнесли, но числительные переводит в цифры:
# «тест гермес один» превращается в «тест гермес 1». Без этой таблицы сравнение
# списков не сойдётся и синк будет добавлять пункт заново на каждом проходе.
_NUMERALS = {
    "один": "1",
    "одна": "1",
    "два": "2",
    "две": "2",
    "три": "3",
    "четыре": "4",
    "пять": "5",
    "шесть": "6",
    "семь": "7",
    "восемь": "8",
    "девять": "9",
    "десять": "10",
    "одиннадцать": "11",
    "двенадцать": "12",
    "тринадцать": "13",
    "четырнадцать": "14",
    "пятнадцать": "15",
    "шестнадцать": "16",
    "семнадцать": "17",
    "восемнадцать": "18",
    "девятнадцать": "19",
    "двадцать": "20",
}


def normalize_item(text: str) -> str:
    """Нормализует название пункта для сравнения HA <-> Алиса."""
    text = text.strip().lower().replace("ё", "е")
    text = " ".join(text.split())
    return " ".join(_NUMERALS.get(word, word) for word in text.split(" "))


class YandexDialogError(Exception):
    """Алиса не ответила текстовой карточкой."""


class YandexDialog:
    """Один текстовый запрос к Алисе за вызов."""

    def __init__(self, session: YandexSession, device_id: str, platform: str | None):
        if not device_id:
            raise YandexDialogError("device_id is required for the cloud dialog")

        self.session = session
        self.device_id = device_id
        self.platform = platform or "yandexstation"
        self._du = ""
        # один диалог за раз: uniproxy не любит параллельные TextInput
        self._lock = asyncio.Lock()

    async def send(self, text: str, timeout: float = 25.0) -> str:
        """Отправляет текст и возвращает текст карточки ответа.

        Бросает YandexDialogError, если карточки нет: значит команда выполнена
        молча (так ведёт себя удаление по номеру) либо навык вернул ошибку.
        """
        async with self._lock:
            try:
                return await self._send(text, timeout)
            except YandexDialogError:
                raise
            except Exception as e:
                # протухшие куки — обычная причина; сессия умеет их обновить
                # по x_token (mobileproxy -> passport/session)
                if not self.session.x_token:
                    raise
                _LOGGER.debug("Cloud dialog failed (%r), refreshing cookies", e)
                if not await self.session.refresh_cookies():
                    raise
                return await self._send(text, timeout)

    async def _send(self, text: str, timeout: float) -> str:
        self._du = uuid.uuid4().hex
        ws = await self.session.client_session.ws_connect(
            UNIPROXY_URL, headers=self._headers(), heartbeat=None, max_msg_size=2**24
        )
        try:
            await ws.send_json(self._sync_payload())
            # uniproxy принимает TextInput только после SynchronizeState:
            # ответ SynchronizeStateResponse содержит SessionId, нам он не нужен
            await asyncio.sleep(1.5)

            request_id = str(uuid.uuid4())
            await ws.send_json(self._text_payload(text, request_id))

            deadline = time.monotonic() + timeout
            while (left := deadline - time.monotonic()) > 0:
                try:
                    msg = await ws.receive(timeout=left)
                except TimeoutError:
                    break

                if msg.type is not WSMsgType.TEXT:
                    continue

                try:
                    data = json.loads(msg.data)
                except ValueError:
                    continue

                if (card := self._extract(data, request_id)) is not None:
                    return card

            raise YandexDialogError("no text answer from Alice")
        finally:
            await ws.close()

    def _headers(self) -> dict:
        jar = self.session.client_session.cookie_jar
        cookies = "; ".join(f"{c.key}={c.value}" for c in jar)
        headers = {
            "Origin": ORIGIN,
            "Referer": ORIGIN + "/",
            "User-Agent": USER_AGENT,
            "x-ya-app-id": APP_ID,
            "x-ya-app-type": "other",
            "x-ya-uuid": self._du,
            # именно device_id колонки: по нему Яндекс понимает, чей это аккаунт
            "x-ya-device-id": self.device_id,
            "x-ya-language": "ru",
            "x-ya-application": json.dumps(
                {
                    "app_id": APP_ID,
                    "uuid": self._du,
                    "device_id": self.device_id,
                    "lang": "ru",
                    "timezone": "Europe/Moscow",
                }
            ),
            "x-ya-experiments": "[]",
        }
        if cookies:
            headers["Cookie"] = cookies
        if self.session.x_token:
            headers["Authorization"] = f"OAuth {self.session.x_token}"
        return headers

    def _application(self) -> dict:
        return {
            "app_id": APP_ID,
            "app_version": APP_VERSION,
            "platform": self.platform,
            "os_version": "Android 13",
            "uuid": self._du,
            "device_id": self.device_id,
            "lang": "ru-RU",
            "client_time": time.strftime("%Y%m%dT%H%M%S"),
            "timezone": "Europe/Moscow",
            "timestamp": str(int(time.time())),
        }

    def _sync_payload(self) -> dict:
        """Рукопожатие сессии: без него TextInput не принимается."""
        return {
            "event": {
                "header": {
                    "namespace": "System",
                    "name": "SynchronizeState",
                    "seqNumber": 1,
                    "messageId": str(uuid.uuid4()),
                },
                "payload": {
                    "auth_token": self.session.x_token or str(uuid.uuid4()),
                    "uuid": self._du,
                    "vins": {
                        "application": {
                            "app_id": APP_ID,
                            "platform": self.platform,
                            "device_id": self.device_id,
                            "uuid": self._du,
                        }
                    },
                    "request": {"experiments": []},
                    "speechkitVersion": "4.16.7",
                    "client_analytics_info": {"client_url": ORIGIN + "/chat/"},
                },
            }
        }

    def _text_payload(self, text: str, request_id: str) -> dict:
        """Текстовый запрос.

        dialog_id равен request_id, то есть каждая команда — отдельный диалог:
        иначе две подряд «Удали ...» склеятся в один контекст и вторая уйдёт в
        уточнение вместо выполнения.
        """
        return {
            "event": {
                "header": {
                    "namespace": "Vins",
                    "name": "TextInput",
                    "messageId": request_id,
                    "seqNumber": 2,
                },
                "payload": {
                    "application": self._application(),
                    "header": {
                        "request_id": request_id,
                        "dialog_id": request_id,
                        "dialog_type": 2,
                    },
                    "request": {
                        "event": {"type": "text_input", "text": text},
                        # голосовой сессии нет, ответ нужен только текстом
                        "voice_session": False,
                        "experiments": [],
                        "additional_options": {"origin_domain": "yandex.ru"},
                        # колонка, от имени которой спрашиваем: по ней определяется
                        # аккаунт и его список покупок
                        "environment_state": {
                            "endpoints": [{"id": self.device_id, "capabilities": []}]
                        },
                    },
                    # обязательные поля протокола, хотя ответ ждём текстовый
                    "format": "audio/ogg;codecs=opus",
                    "mime": "audio/ogg;codecs=opus",
                    "topic": "general",
                    "punctuation": False,
                },
            }
        }

    @staticmethod
    def _extract(data: dict, request_id: str) -> str | None:
        """Достаёт текст ответа из кадра или возвращает None для чужих кадров.

        В одном соединении приходит несколько кадров (стриминг, InputStartAck,
        карточка), поэтому сверяем request_id/ref_message_id. Ошибку навыка
        превращаем в исключение, чтобы вызывающий код не принял её за пустой
        список и не перезаписал HA пустотой.
        """
        payload: dict = (data.get("directive") or {}).get("payload") or {}

        header: dict = payload.get("header") or {}
        if request_id not in (header.get("request_id"), header.get("ref_message_id")):
            return None

        if error := (payload.get("error") or {}).get("message"):
            raise YandexDialogError(error)

        response: dict = payload.get("response") or {}
        for card in (response.get("cards") or []) + (
            [response["card"]] if response.get("card") else []
        ):
            if text := card.get("text"):
                return text

        return None
