import logging
import os
import re
import uuid
from datetime import datetime
from logging import Logger

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import DOMAIN as DOMAIN_MP
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

# remove uiid, IP
RE_PRIVATE = re.compile(
    r"\b([a-z0-9]{20}|[A-Z0-9]{24}|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")

NOTIFY_TEXT = (
    '<a href="%s" target="_blank">Открыть лог<a> | '
    '[README](https://github.com/AlexxIT/YandexStation)')

HTML = ('<!DOCTYPE html><html><head><title>YandexStation</title>'
        '<meta http-equiv="refresh" content="%s"></head>'
        '<body><pre>%s</pre></body></html>')


class YandexDebug(logging.Handler, HomeAssistantView):
    name = "yandex_station_debug"
    requires_auth = False

    text = ''

    def __init__(self, hass: HomeAssistantType, logger: Logger):
        super().__init__()

        logger.addHandler(self)
        logger.setLevel(logging.DEBUG)

        hass.loop.create_task(self.system_info(hass))

        # random url because without authorization!!!
        self.url = f"/{uuid.uuid4()}"

        hass.http.register_view(self)
        hass.components.persistent_notification.async_create(
            NOTIFY_TEXT % self.url, title="YandexStation DEBUG")

    @staticmethod
    async def system_info(hass):
        info = await hass.helpers.system_info.async_get_system_info()
        info.pop('installation_type', None)  # fix HA v0.109.6
        info.pop('timezone')
        _LOGGER.debug(f"SysInfo: {info}")

    def handle(self, rec: logging.LogRecord) -> None:
        dt = datetime.fromtimestamp(rec.created).strftime("%Y-%m-%d %H:%M:%S")
        module = 'main' if rec.module == '__init__' else rec.module
        # remove private data
        msg = RE_PRIVATE.sub("...", str(rec.msg))
        self.text += f"{dt}  {rec.levelname:7}  {module:13}  {msg}\n"

    async def get(self, request: web.Request):
        reload = request.query.get('r', '')
        return web.Response(text=HTML % (reload, self.text),
                            content_type="text/html")


def update_form(name: str, **kwargs):
    return {
        'command': 'serverAction',
        'serverActionEventPayload': {
            'type': 'server_action',
            'name': 'update_form',
            'payload': {
                'form_update': {
                    'name': name,
                    'slots': [{'type': 'string', 'name': k, 'value': v}
                              for k, v in kwargs.items()]
                },
                'resubmit': True
            }
        }
    }


def find_station(devices: list, name: str = None):
    """Найти станцию по ID, имени или просто первую попавшуюся."""
    for device in devices:
        if device.get('entity') and (device['device_id'] == name or
                                     device['name'] == name or name is None):
            return device['entity'].entity_id
    return None


async def error(hass: HomeAssistantType, text: str):
    _LOGGER.error(text)
    hass.components.persistent_notification.async_create(
        text, title="YandexStation ERROR")


def clean_v1(hass_dir):
    """Подчищаем за первой версией компонента."""
    path = hass_dir.path('.yandex_station.txt')
    if os.path.isfile(path):
        os.remove(path)

    path = hass_dir.path('.yandex_station_cookies.pickle')
    if os.path.isfile(path):
        os.remove(path)


async def has_custom_icons(hass: HomeAssistantType):
    # GUI off mode
    if 'lovelace' not in hass.data:
        return False

    resources = hass.data['lovelace']['resources']
    await resources.async_get_info()
    for resource in resources.async_items():
        if '/yandex-icons.js' in resource['url']:
            return True
    return False


def play_video_by_descriptor(provider: str, item_id: str):
    return {
        'command': 'serverAction',
        'serverActionEventPayload': {
            'type': 'server_action',
            'name': 'bass_action',
            'payload': {
                'data': {
                    'video_descriptor': {
                        'provider_item_id': item_id,
                        'provider_name': provider
                    }
                },
                'name': 'quasar.play_video_by_descriptor'
            }
        }
    }


RE_MEDIA = {
    'youtube': re.compile(
        r'https://(?:youtu\.be/|www\.youtube\.com/.+?v=)([0-9A-Za-z_-]{11})'),
    'hd.kinopoisk': re.compile(
        r'https://hd\.kinopoisk\.ru/(?:.*)([0-9a-z]{32})'),
    'music.yandex.playlist': re.compile(
        r'https://music\.yandex\.ru/users/(.+?)/playlists/(\d+)'),
    'music.yandex': re.compile(
        r'https://music\.yandex\.ru/(?:.*)(artist|track|album)/(\d+)'),
    'kinopoisk': re.compile(
        r'https?://www\.kinopoisk\.ru/film/(\d+)/')
}


async def get_media_payload(text: str, session):
    for k, v in RE_MEDIA.items():
        m = v.search(text)
        if m:
            if k == 'youtube':
                return play_video_by_descriptor('youtube', m[1])

            elif k == 'hd.kinopoisk':
                return play_video_by_descriptor('kinopoisk', m[1])

            elif k == 'music.yandex.playlist':
                try:
                    r = await session.get(
                        'https://music.yandex.ru/handlers/library.jsx',
                        params={'owner': m[1]})
                    resp = await r.json()
                    return {
                        'command': 'playMusic',
                        'type': 'playlist',
                        'id': f"{resp['owner']['uid']}:{m[2]}",
                    }

                except:
                    return None

            elif k == 'music.yandex':
                return {
                    'command': 'playMusic',
                    'type': m[1],
                    'id': m[2],
                }

            elif k == 'kinopoisk':
                try:
                    r = await session.get(
                        'https://ott-widget.kinopoisk.ru/ott/api/'
                        'kp-film-status/', params={'kpFilmId': m[1]})
                    resp = await r.json()
                    return play_video_by_descriptor('kinopoisk', resp['uuid'])

                except:
                    return None

    return None


async def get_zeroconf_singleton(hass: HomeAssistantType):
    try:
        # Home Assistant 0.110.0 and above
        from homeassistant.components.zeroconf import async_get_instance
        return await async_get_instance(hass)
    except:
        from zeroconf import Zeroconf
        return Zeroconf()
