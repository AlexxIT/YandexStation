import asyncio
import logging
import secrets
import time
from contextlib import suppress
from urllib.parse import urljoin, urlparse

import jwt
from aiohttp import ClientError, ClientSession, ClientTimeout, hdrs, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import async_process_play_media_url
from homeassistant.core import HomeAssistant
from homeassistant.helpers import network
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

MIME_TYPES = {
    "flac": "audio/x-flac",
    "aac": "audio/aac",
    "he.aac": "audio/aac",
    "mp3": "audio/mpeg",
    # https://www.rfc-editor.org/rfc/rfc4337.txt
    "flac.mp4": "audio/mp4",
    "aac.mp4": "audio/mp4",
    "he.aac.mp4": "audio/mp4",
    # application/vnd.apple.mpegurl
    "m3u8": "application/x-mpegURL",
    "ts": "video/MP2T",
    "gif": "image/gif",
    "mp4": "video/mp4",
}


def get_ext(url: str) -> str:
    return urlparse(url).path.split(".")[-1]


def get_url(url: str, ext: str = None, expires: int = 3600) -> str:
    assert StreamView.hass_url
    assert url.startswith(("http://", "https://", "/")), url

    ext = ext.replace("-", ".") if ext else get_ext(url)
    assert ext in MIME_TYPES, ext

    # using token for security reason
    payload: dict[str, str | int] = {"url": url}
    if expires:
        payload["exp"] = int(time.time()) + expires
    token = jwt.encode(payload, StreamView.key, "HS256")
    return f"{StreamView.hass_url}/api/yandex_station/{token}.{ext}"


async def get_hls(session: ClientSession, url: str) -> str:
    async with session.get(url) as r:
        lines = (await r.text()).splitlines()
        for i, item in enumerate(lines):
            item = item.strip()
            if not item or item.startswith("#"):
                continue
            # should use r.url, not url, because redirects
            item = urljoin(str(r.url), item)
            lines[i] = get_url(item)
        return "\n".join(lines)


def copy_headers(headers: dict, names: tuple) -> dict:
    return {k: v for k in names if (v := headers.get(k))}


CONTENT_TYPES = {
    "audio/aac": "aac",
    "audio/mpeg": "mp3",
    "audio/x-flac": "flac",
    "application/vnd.apple.mpegurl": "m3u8",
    "application/x-mpegURL": "m3u8",
}

REQUEST_HEADERS = (hdrs.RANGE,)
RESPONSE_HEADERS = (hdrs.ACCEPT_RANGES, hdrs.CONTENT_LENGTH, hdrs.CONTENT_RANGE)
STREAM_TIMEOUT = ClientTimeout(sock_connect=10, sock_read=10)


async def get_content_type(session: ClientSession, url: str) -> str | None:
    try:
        async with session.head(url) as r:
            if r.content_type.startswith("text/html"):
                # fix Icecast bug - return text/html on HEAD
                # https://github.com/AlexxIT/YandexStation/issues/696
                async with session.get(url) as r2:
                    return CONTENT_TYPES.get(r2.content_type)
            return CONTENT_TYPES.get(r.content_type)
    except Exception as e:
        _LOGGER.debug(f"Can't get content type: {repr(e)}")
        return None


class StreamView(HomeAssistantView):
    requires_auth = False

    url = "/api/yandex_station/{token:[\\w-]+.[\\w-]+.[\\w-]+}.{ext}"
    name = "api:yandex_station"

    hass: HomeAssistant = None
    hass_url: str = None
    key: str = None

    def __init__(self, hass: HomeAssistant):
        self.session = async_get_clientsession(hass)

        StreamView.hass = hass
        StreamView.key = secrets.token_hex()

        try:
            StreamView.hass_url = network.get_url(hass, allow_external=False)
            _LOGGER.debug(f"Локальный адрес Home Assistant: {StreamView.hass_url}")
        except Exception as e:
            _LOGGER.warning(f"Ошибка получения локального адреса Home Assistant: {e}")

    def get_url(self, url: str) -> str:
        if url[0] != "/":
            return url
        return async_process_play_media_url(self.hass, url)

    async def head(self, request: web.Request, token: str, ext: str):
        try:
            data = jwt.decode(token, StreamView.key, "HS256")
        except jwt.InvalidTokenError:
            return web.HTTPNotFound()

        _LOGGER.debug(f"Stream.{ext} HEAD {data}")

        url = self.get_url(data["url"])

        headers = copy_headers(request.headers, REQUEST_HEADERS)
        async with self.session.head(url, headers=headers) as r:
            headers = copy_headers(r.headers, RESPONSE_HEADERS)
            headers[hdrs.CONTENT_TYPE] = MIME_TYPES[ext]
            return web.Response(status=r.status, headers=headers)

    async def get(self, request: web.Request, token: str, ext: str):
        try:
            data = jwt.decode(token, StreamView.key, "HS256")
        except jwt.InvalidTokenError:
            return web.HTTPNotFound()

        _LOGGER.debug(f"Stream.{ext} GET {data}")

        url = self.get_url(data["url"])

        try:
            if ext == "m3u8":
                body = await get_hls(self.session, url)
                return web.Response(
                    body=body,
                    headers={
                        hdrs.ACCESS_CONTROL_ALLOW_HEADERS: "*",
                        hdrs.ACCESS_CONTROL_ALLOW_ORIGIN: "*",
                        hdrs.CONTENT_TYPE: MIME_TYPES[ext],
                    },
                )

            headers = copy_headers(request.headers, REQUEST_HEADERS)
            async with self.session.get(
                url, headers=headers, timeout=STREAM_TIMEOUT
            ) as r:
                headers = copy_headers(r.headers, RESPONSE_HEADERS)
                headers[hdrs.CONTENT_TYPE] = MIME_TYPES[ext]

                if ext == "ts":
                    headers[hdrs.ACCESS_CONTROL_ALLOW_HEADERS] = "*"
                    headers[hdrs.ACCESS_CONTROL_ALLOW_ORIGIN] = "*"

                response = web.StreamResponse(status=r.status, headers=headers)
                response.force_close()

                await response.prepare(request)

                try:
                    while data := await r.content.readany():
                        await response.write(data)
                except ClientError as e:
                    _LOGGER.debug(f"Streaming client error: {repr(e)}")
                except TimeoutError as e:
                    _LOGGER.debug(f"Streaming timeout: {repr(e)}")

                return response
        except:
            pass
