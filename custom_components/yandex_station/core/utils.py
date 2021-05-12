import json
import logging
import os
import re
import uuid
from datetime import datetime
from logging import Logger

from aiohttp import web, ClientSession
from homeassistant.components import frontend
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
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
        if device.get('entity') and (
                device['quasar_info']['device_id'] == name or
                device['name'] == name or name is None
        ):
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
    'kinopoisk': re.compile(r'https://hd\.kinopoisk\.ru/.*([0-9a-z]{32})'),
    'strm': re.compile(r'https://yandex.ru/efir\?.*stream_id=([^&]+)'),
    'music.yandex.playlist': re.compile(
        r'https://music\.yandex\.[a-z]+/users/(.+?)/playlists/(\d+)'),
    'music.yandex': re.compile(
        r'https://music\.yandex\.[a-z]+/.*(artist|track|album)/(\d+)'),
    'kinopoisk.id': re.compile(r'https?://www\.kinopoisk\.ru/film/(\d+)/'),
    'yavideo': re.compile(
        r'(https?://ok\.ru/video/\d+|https?://vk.com/video-?[0-9_]+)'),
    'vk': re.compile(r'https://vk\.com/.*(video-?[0-9_]+)'),
}


async def get_media_payload(text: str, session):
    for k, v in RE_MEDIA.items():
        m = v.search(text)
        if m:
            if k in ('youtube', 'kinopoisk', 'strm', 'yavideo'):
                return play_video_by_descriptor(k, m[1])

            elif k == 'vk':
                url = 'https://vk.com/' + m[1]
                return play_video_by_descriptor('yavideo', url)

            elif k == 'music.yandex.playlist':
                uid = await get_userid_v2(session, m[1])
                if uid:
                    return {
                        'command': 'playMusic',
                        'type': 'playlist',
                        'id': f"{uid}:{m[2]}",
                    }

            elif k == 'music.yandex':
                return {
                    'command': 'playMusic',
                    'type': m[1],
                    'id': m[2],
                }

            elif k == 'kinopoisk.id':
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


RE_ID3 = re.compile(br'(Text|TIT2)(....)\x00\x00\x03(.+?)\x00',
                    flags=re.DOTALL)


async def get_tts_message(session: ClientSession, url: str):
    """Текст сообщения записывается в файл в виде ID3-тегов. Нужно скачать файл
    и прочитать этот тег. В старых версиях ХА валидный ID3-тег, а в новых -
    битый.
    """
    try:
        r = await session.get(url, ssl=False)
        data = await r.read()

        m = RE_ID3.findall(data)
        if len(m) == 1 and m[0][0] == b'TIT2':
            # old Hass version has valid ID3 tags with `TIT2` for Title
            _LOGGER.debug(f"Получение TTS из ID3")
            m = m[0]
        elif len(m) == 3 and m[2][0] == b'Text':
            # latest Hass version has bug with `Text` for all tags
            # there are 3 tags and the last one we need
            _LOGGER.debug(f"Получение TTS из битого ID3")
            m = m[2]
        else:
            _LOGGER.debug(f"Невозможно получить TTS: {data}")
            return None

        # check tag value length
        if int.from_bytes(m[1], 'big') - 2 == len(m[2]):
            return m[2].decode('utf-8')

    except:
        _LOGGER.exception("Ошибка получения сообщения TTS")

    return None


# noinspection PyProtectedMember
def fix_recognition_lang(hass: HomeAssistantType, folder: str, lng: str):
    path = frontend._frontend_root(None).joinpath(folder)
    for child in path.iterdir():
        # find all chunc.xxxx.js files
        if child.suffix != '.js' and 'chunk.' not in child.name:
            continue

        with open(child, 'rb') as f:
            raw = f.read()

        # find chunk file with recognition code
        if b'this.recognition.lang=' not in raw:
            continue

        raw = raw.replace(b'en-US', lng.encode())

        async def recognition_lang(request):
            _LOGGER.debug("Send fixed recognition lang to client")
            return web.Response(body=raw,
                                content_type='application/javascript')

        hass.http.app.router.add_get('/frontend_latest/' + child.name,
                                     recognition_lang)

        resource = hass.http.app.router._resources.pop()
        hass.http.app.router._resources.insert(40, resource)

        _LOGGER.debug(f"Fix recognition lang in {folder} to {lng}")

        return


RE_CLOUD_TEXT = re.compile(r'(<.+?>|[^А-Яа-яЁёA-Za-z0-9-,!.:=? ]+)')
RE_CLOUD_SPACE = re.compile(r'  +')


def fix_cloud_text(text: str) -> str:
    """В облачном тексте есть ограничения:
    1. Команда Алисе может содержать только кириллицу, латиницу, цифры и
    спецсимволы: "-,!.:=?".
    2. Команда Алисе должна быть не длиннее 100 символов
    3. Нельзя использовать 2 пробела подряд (PS: что с ними не так?!)
    """
    text = text.strip()
    text = RE_CLOUD_TEXT.sub('', text)
    text = RE_CLOUD_SPACE.sub(' ', text)
    return text[:100]


# https://music.yandex.ru/users/alexey.khit/playlists
async def get_userid_v1(session: ClientSession, username: str,
                        playlist_id: str):
    try:
        payload = {
            'owner': username, 'kinds': playlist_id, 'light': 'true',
            'withLikesCount': 'false', 'lang': 'ru',
            'external-domain': 'music.yandex.ru',
            'overembed': 'false'
        }
        r = await session.get(
            'https://music.yandex.ru/handlers/playlist.jsx',
            params=payload)
        resp = await r.json()
        return resp['playlist']['owner']['uid']
    except:
        return None


async def get_userid_v2(session: ClientSession, username: str):
    try:
        r = await session.get(
            f"https://music.yandex.ru/users/{username}/playlists")
        resp = await r.text()
        return re.search(r'"uid":"(\d+)",', resp)[1]
    except:
        return None


def dump_capabilities(data: dict) -> dict:
    for k in ('id', 'request_id', 'updates_url', 'external_id'):
        if k in data:
            data.pop(k)
    return data


def load_token_from_json(hass: HomeAssistant):
    """Load token from .yandex_station.json"""
    filename = hass.config.path('.yandex_station.json')
    if os.path.isfile(filename):
        with open(filename, 'rt') as f:
            raw = json.load(f)
        return raw['main_token']['access_token']
    return None
