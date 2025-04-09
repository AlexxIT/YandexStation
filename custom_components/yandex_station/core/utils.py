import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime
from logging import Logger
from typing import Callable, List

from aiohttp import ClientSession, web
from homeassistant.components import frontend
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import network
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    async_track_template_result,
)
from homeassistant.helpers.template import Template
from yarl import URL

from .const import CONF_MEDIA_PLAYERS, DATA_CONFIG, DOMAIN

_LOGGER = logging.getLogger(__name__)

# remove uiid, IP
RE_PRIVATE = re.compile(
    r"\b([a-z0-9]{20}|[A-Z0-9]{24}|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b"
)

NOTIFY_TEXT = (
    '<a href="%s" target="_blank">Открыть лог<a> | '
    "[README](https://github.com/AlexxIT/YandexStation)"
)

HTML = (
    "<!DOCTYPE html><html><head><title>YandexStation</title>"
    '<meta http-equiv="refresh" content="%s"></head>'
    "<body><pre>%s</pre></body></html>"
)


class YandexDebug(logging.Handler, HomeAssistantView):
    name = "yandex_station_debug"
    requires_auth = False

    text = ""

    def __init__(self, hass: HomeAssistant, logger: Logger):
        super().__init__()

        logger.addHandler(self)
        logger.setLevel(logging.DEBUG)

        hass.loop.create_task(self.system_info(hass))

        # random url because without authorization!!!
        self.url = f"/{uuid.uuid4()}"

        hass.http.register_view(self)
        hass.components.persistent_notification.async_create(
            NOTIFY_TEXT % self.url, title="YandexStation DEBUG"
        )

    @staticmethod
    async def system_info(hass):
        info = await hass.helpers.system_info.async_get_system_info()
        info.pop("installation_type", None)  # fix HA v0.109.6
        info.pop("timezone")
        _LOGGER.debug(f"SysInfo: {info}")

    def handle(self, rec: logging.LogRecord) -> None:
        dt = datetime.fromtimestamp(rec.created).strftime("%Y-%m-%d %H:%M:%S")
        module = "main" if rec.module == "__init__" else rec.module
        # remove private data
        msg = RE_PRIVATE.sub("...", str(rec.msg))
        self.text += f"{dt}  {rec.levelname:7}  {module:13}  {msg}\n"

    async def get(self, request: web.Request):
        reload = request.query.get("r", "")
        return web.Response(text=HTML % (reload, self.text), content_type="text/html")


def update_form(name: str, **kwargs):
    return {
        "command": "serverAction",
        "serverActionEventPayload": {
            "type": "server_action",
            "name": "update_form",
            "payload": {
                "form_update": {
                    "name": name,
                    "slots": [
                        {"type": "string", "name": k, "value": v}
                        for k, v in kwargs.items()
                    ],
                },
                "resubmit": True,
            },
        },
    }


def find_station(devices, name: str = None):
    """Найти станцию по ID, имени или просто первую попавшуюся."""
    for device in devices:
        if device.get("entity") and (
            device["quasar_info"]["device_id"] == name
            or device["name"] == name
            or name is None
        ):
            return device["entity"].entity_id
    return None


async def error(hass: HomeAssistant, text: str):
    _LOGGER.error(text)
    hass.components.persistent_notification.async_create(
        text, title="YandexStation ERROR"
    )


def clean_v1(hass_dir):
    """Подчищаем за первой версией компонента."""
    path = hass_dir.path(".yandex_station.txt")
    if os.path.isfile(path):
        os.remove(path)

    path = hass_dir.path(".yandex_station_cookies.pickle")
    if os.path.isfile(path):
        os.remove(path)


async def has_custom_icons(hass: HomeAssistant):
    lovelace = hass.data.get("lovelace")

    # GUI off mode
    if not lovelace:
        return False

    resources = (
        lovelace.resources if hasattr(lovelace, "resources") else lovelace["resources"]
    )
    await resources.async_get_info()

    return any(
        "/yandex-icons.js" in resource["url"] for resource in resources.async_items()
    )


def play_video_by_descriptor(provider: str, item_id: str):
    return {
        "command": "serverAction",
        "serverActionEventPayload": {
            "type": "server_action",
            "name": "bass_action",
            "payload": {
                "data": {
                    "video_descriptor": {
                        "provider_item_id": item_id,
                        "provider_name": provider,
                    }
                },
                "name": "quasar.play_video_by_descriptor",
            },
        },
    }


RE_MEDIA = {
    "youtube": re.compile(
        r"https://(?:youtu\.be/|www\.youtube\.com/.+?v=)([0-9A-Za-z_-]{11})"
    ),
    "kinopoisk": re.compile(r"https://hd\.kinopoisk\.ru/.*([0-9a-z]{32})"),
    "strm": re.compile(r"https://yandex.ru/efir\?.*stream_id=([^&]+)"),
    "music.yandex.playlist": re.compile(
        r"https://music\.yandex\.[a-z]+/users/(.+?)/playlists/(\d+)"
    ),
    "music.yandex": re.compile(
        r"https://music\.yandex\.[a-z]+/.*(artist|track|album)/(\d+)"
    ),
    "kinopoisk.id": re.compile(r"https?://www\.kinopoisk\.ru/film/(\d+)/"),
    "yavideo": re.compile(
        r"(https?://ok\.ru/video/\d+|https?://vk.com/video-?[0-9_]+)"
    ),
    "vk": re.compile(r"https://vk\.com/.*(video-?[0-9_]+)"),
    "bookmate": re.compile(r"https://books\.yandex\.ru/audiobooks/(\w+)"),
}


async def get_media_payload(session, text: str) -> dict | None:
    for k, v in RE_MEDIA.items():
        if m := v.search(text):
            if k in ("youtube", "kinopoisk", "strm", "yavideo"):
                return play_video_by_descriptor(k, m[1])

            elif k == "vk":
                url = f"https://vk.com/{m[1]}"
                return play_video_by_descriptor("yavideo", url)

            elif k == "music.yandex.playlist":
                if uid := await get_playlist_uid(session, m[1], m[2]):
                    return {
                        "command": "playMusic",
                        "type": "playlist",
                        "id": f"{uid}:{m[2]}",
                    }

            elif k == "music.yandex":
                return {
                    "command": "playMusic",
                    "type": m[1],
                    "id": m[2],
                }

            elif k == "kinopoisk.id":
                try:
                    r = await session.get(
                        "https://ott-widget.kinopoisk.ru/ott/api/kp-film-status/",
                        params={"kpFilmId": m[1]},
                    )
                    resp = await r.json()
                    return play_video_by_descriptor("kinopoisk", resp["uuid"])

                except:
                    return None

            elif k == "bookmate":
                try:
                    r = await session.post(
                        "https://api-gateway-rest.bookmate.yandex.net/audiobook/album",
                        json={"audiobook_uuid": m[1]},
                    )
                    resp = await r.json()
                    return {
                        "command": "playMusic",
                        "type": "album",
                        "id": resp["album_id"],
                    }
                except:
                    return None

    return None


async def get_zeroconf_singleton(hass: HomeAssistant):
    try:
        # Home Assistant 0.110.0 and above
        from homeassistant.components.zeroconf import async_get_instance

        return await async_get_instance(hass)
    except:
        from zeroconf import Zeroconf

        return Zeroconf()


RE_ID3 = re.compile(rb"(Text|TIT2)(....)\x00\x00\x03(.+?)\x00", flags=re.DOTALL)


async def get_tts_message(session: ClientSession, url: str):
    """Текст сообщения записывается в файл в виде ID3-тегов. Нужно скачать файл
    и прочитать этот тег. В старых версиях ХА валидный ID3-тег, а в новых -
    битый.
    """
    try:
        r = await session.get(url, ssl=False)
        data = await r.read()

        m = RE_ID3.findall(data)
        if len(m) == 1 and m[0][0] == b"TIT2":
            # old Hass version has valid ID3 tags with `TIT2` for Title
            _LOGGER.debug("Получение TTS из ID3")
            m = m[0]
        elif len(m) == 3 and m[2][0] == b"Text":
            # latest Hass version has bug with `Text` for all tags
            # there are 3 tags and the last one we need
            _LOGGER.debug("Получение TTS из битого ID3")
            m = m[2]
        else:
            _LOGGER.debug(f"Невозможно получить TTS: {data}")
            return None

        # check tag value length
        if int.from_bytes(m[1], "big") - 2 == len(m[2]):
            return m[2].decode("utf-8")

    except:
        _LOGGER.exception("Ошибка получения сообщения TTS")

    return None


# noinspection PyProtectedMember
def fix_recognition_lang(hass: HomeAssistant, folder: str, lng: str):
    path = frontend._frontend_root(None).joinpath(folder)
    for child in path.iterdir():
        # find all chunc.xxxx.js files
        if child.suffix != ".js" and "chunk." not in child.name:
            continue

        with open(child, "rb") as f:
            raw = f.read()

        # find chunk file with recognition code
        if b"this.recognition.lang=" not in raw:
            continue

        raw = raw.replace(b"en-US", lng.encode())

        async def recognition_lang(request):
            _LOGGER.debug("Send fixed recognition lang to client")
            return web.Response(body=raw, content_type="application/javascript")

        hass.http.app.router.add_get(f"/frontend_latest/{child.name}", recognition_lang)

        resource = hass.http.app.router._resources.pop()
        hass.http.app.router._resources.insert(40, resource)

        _LOGGER.debug(f"Fix recognition lang in {folder} to {lng}")

        return


def fix_cloud_text(text: str) -> str:
    # на июнь 2023 единственное ограничение - 100 символов
    text = re.sub(r"  +", " ", text)
    return text.strip()[:100]


async def get_playlist_uid(session, username: str, playlist_id: str) -> int | None:
    try:
        r = await session.get(
            f"https://api.music.yandex.net/users/{username}/playlists/{playlist_id}",
        )
        resp = await r.json()
        return resp["result"]["owner"]["uid"]
    except:
        return None


def dump_capabilities(data: dict) -> dict:
    for k in ("id", "request_id", "updates_url", "external_id"):
        if k in data:
            data.pop(k)
    return data


def load_token_from_json(hass: HomeAssistant):
    """Load token from .yandex_station.json"""
    filename = hass.config.path(".yandex_station.json")
    if os.path.isfile(filename):
        with open(filename, "rt") as f:
            raw = json.load(f)
        return raw["main_token"]["access_token"]
    return None


@callback
def get_media_players(hass: HomeAssistant, speaker_id: str) -> List[dict]:
    """Get all Hass media_players not from yandex_station with support
    play_media service.
    """
    # check entity_components because MPD not in entity_registry and DLNA has
    # wrong supported_features
    try:
        if conf := hass.data[DOMAIN][DATA_CONFIG].get(CONF_MEDIA_PLAYERS):
            if isinstance(conf, dict):
                return [{"entity_id": k, "name": v} for k, v in conf.items()]
            if isinstance(conf, list):
                # conf item should have entity_id and name
                # conf item may have speaker_id filter
                return [
                    item
                    for item in conf
                    if "entity_id" in item
                    and "name" in item
                    and speaker_id in item.get("speaker_id", speaker_id)
                ]

        ec: EntityComponent = hass.data["entity_components"]["media_player"]
        return [
            {
                "entity_id": entity.entity_id,
                "name": (
                    (entity.registry_entry and entity.registry_entry.name)
                    or entity.name
                    or entity.entity_id
                ),
            }
            for entity in ec.entities
            if (
                entity.platform.platform_name != DOMAIN
                and entity.supported_features & MediaPlayerEntityFeature.PLAY_MEDIA
            )
        ]
    except Exception as e:
        _LOGGER.warning("Can't get media_players", exc_info=e)
        return []


def encode_media_source(query: dict) -> str:
    """Convert message param as URL query and all other params as hex path."""
    if "message" in query:
        message = query.pop("message")
        return f"{encode_media_source(query)}?message={message}"
    return URL.build(query=query).query_string.encode().hex()


def decode_media_source(media_id: str) -> dict:
    url = URL(media_id)
    try:
        url = URL(f"?{bytes.fromhex(url.name).decode()}&{url.query_string}")
    except Exception:
        pass
    return dict(url.query)


def track_template(hass: HomeAssistant, template: str, update: Callable) -> Callable:
    template = Template(template, hass)
    update(template.async_render())

    # important to use async because from sync action will be problems with update state
    async def action(event, updates: list[TrackTemplateResult]):
        update(next(i.result for i in updates))

    track = async_track_template_result(
        hass, [TrackTemplate(template=template, variables=None)], action
    )
    return track.async_remove


def get_entity(hass: HomeAssistant, entity_id: str) -> Entity | None:
    try:
        ec: EntityComponent = hass.data["entity_components"]["media_player"]
        return next(e for e in ec.entities if e.entity_id == entity_id)
    except:
        pass
    return None


MIME_TYPES = {
    "flac": "audio/x-flac",
    "aac": "audio/aac",
    "he.aac": "audio/aac",
    "mp3": "audio/mpeg",
    "flac.mp4": "video/mp4",
    "aac.mp4": "video/mp4",
    "he.aac.mp4": "video/mp4",
}


class StreamingView(HomeAssistantView):
    requires_auth = False

    url = "/api/yandex_station/{sid}/{uid:[0-9a-f]+}.{ext}"
    name = "api:yandex_station"

    links: dict = {}

    def __init__(self, hass: HomeAssistant):
        self.session = async_get_clientsession(hass)

    @staticmethod
    def get_url(hass: HomeAssistant, sid: str, url: str, ext: str):
        ext = ext.replace("-", ".")
        assert ext in MIME_TYPES
        sid = sid.lower()
        uid = hashlib.md5(url.encode()).hexdigest()
        StreamingView.links[sid] = url
        local_url = f"{network.get_url(hass)}/api/yandex_station/{sid}/{uid}.{ext}"
        _LOGGER.debug(f"Streaming URL: {local_url}")
        return local_url

    async def head(self, request: web.Request, sid: str, uid: str, ext: str):
        url: str = self.links.get(sid)
        if not url or hashlib.md5(url.encode()).hexdigest() != uid:
            return web.HTTPNotFound()

        headers = {"Range": r} if (r := request.headers.get("Range")) else None
        async with self.session.head(url, headers=headers) as r:
            response = web.Response(status=r.status)
            response.headers.update(r.headers)
            # important for DLNA players
            response.headers["Content-Type"] = MIME_TYPES[ext]
            return response

    async def get(self, request: web.Request, sid: str, uid: str, ext: str):
        url: str = self.links.get(sid)
        if not url or hashlib.md5(url.encode()).hexdigest() != uid:
            return web.HTTPNotFound()

        try:
            headers = {"Range": r} if (r := request.headers.get("Range")) else None
            async with self.session.get(url, headers=headers) as r:
                response = web.StreamResponse(status=r.status)
                response.headers.update(r.headers)
                response.headers["Content-Type"] = MIME_TYPES[ext]

                await response.prepare(request)

                # same chunks as default web.FileResponse
                async for chunk in r.content.iter_chunked(256 * 1024):
                    await response.write(chunk)
        except Exception:
            pass
