import logging
import os
import re
import uuid
from datetime import datetime
from logging import Logger
from typing import Optional

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


def find_station(hass, device: str = None) -> Optional[str]:
    """Найти станцию по ID, имени или просто первую попавшуюся."""
    from .media_player import YandexStation
    for entity in hass.data[DATA_INSTANCES][DOMAIN_MP].entities:
        if isinstance(entity, YandexStation):
            if device is None or entity.is_device(device):
                return entity.entity_id
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
