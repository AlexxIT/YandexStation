import logging
import secrets
import time
from urllib.parse import urljoin, urlparse

import jwt
from aiohttp import ClientSession, web
from homeassistant.components.http import HomeAssistantView
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
}


def get_ext(url: str) -> str:
    return urlparse(url).path.split(".")[-1]


def get_url(url: str, ext: str = None, expires: float = 3600) -> str:
    ext = ext.replace("-", ".") if ext else get_ext(url)
    assert ext in MIME_TYPES

    # using token for security reason
    payload = {"url": url, "exp": time.time() + expires}
    token = jwt.encode(payload, StreamView.key, "HS256")
    return f"{StreamView.hass_url}/api/yandex_station/{token}.{ext}"


async def get_hls(session: ClientSession, url: str) -> str:
    async with session.get(url) as r:
        lines = (await r.text()).splitlines()
        for i, item in enumerate(lines):
            if item.startswith("#"):
                continue
            if item.startswith("/"):
                item = urljoin(url, item)
            lines[i] = get_url(item)
        return "\n".join(lines)


class StreamView(HomeAssistantView):
    requires_auth = False

    url = "/api/yandex_station/{token:[a-zA-Z0-9._-]+}.{ext}"
    name = "api:yandex_station"

    hass: HomeAssistant = None
    hass_url: str = None
    key: str = None

    def __init__(self, hass: HomeAssistant):
        self.session = async_get_clientsession(hass)

        StreamView.hass = hass
        StreamView.hass_url = network.get_url(hass)
        StreamView.key = secrets.token_hex()

    async def head(self, request: web.Request, token: str, ext: str):
        try:
            data = jwt.decode(token, StreamView.key, "HS256")
        except jwt.InvalidTokenError:
            return web.HTTPNotFound()

        if time.time() > data["exp"]:
            return web.HTTPForbidden()

        _LOGGER.debug("Stream HEAD " + data["url"])

        headers = {"Range": r} if (r := request.headers.get("Range")) else None
        async with self.session.head(data["url"], headers=headers) as r:
            response = web.Response(status=r.status, headers=r.headers)
            # important for DLNA players
            response.headers["Content-Type"] = MIME_TYPES[ext]
            return response

    async def get(self, request: web.Request, token: str, ext: str):
        try:
            data = jwt.decode(token, StreamView.key, "HS256")
        except jwt.InvalidTokenError:
            return web.HTTPNotFound()

        if time.time() > data["exp"]:
            return web.HTTPForbidden()

        _LOGGER.debug("Stream GET " + data["url"])

        try:
            if ext == "m3u8":
                body = await get_hls(self.session, data["url"])
                return web.Response(
                    body=body,
                    headers={
                        "Access-Control-Allow-Headers": "*",
                        "Access-Control-Allow-Origin": "*",
                        "Content-Type": MIME_TYPES[ext],
                    },
                )

            headers = {"Range": r} if (r := request.headers.get("Range")) else None
            async with self.session.get(data["url"], headers=headers) as r:
                response = web.StreamResponse(status=r.status, headers=r.headers)
                response.headers["Content-Type"] = MIME_TYPES[ext]

                if ext == "ts":
                    response.headers["Access-Control-Allow-Headers"] = "*"
                    response.headers["Access-Control-Allow-Origin"] = "*"

                await response.prepare(request)

                async for chunk in r.content.iter_chunked(16 * 1024):
                    await response.write(chunk)
        except Exception:
            pass
