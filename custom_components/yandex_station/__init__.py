import ipaddress
import json
import logging
from typing import Callable

from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_ID, \
    ATTR_MEDIA_CONTENT_TYPE, DOMAIN as DOMAIN_MP, SERVICE_PLAY_MEDIA
from homeassistant.components.tts import ATTR_MESSAGE, \
    DOMAIN as DOMAIN_TTS
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN, \
    ATTR_ENTITY_ID
from homeassistant.core import ServiceCall
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.setup import async_setup_component

from zeroconf import ServiceBrowser, Zeroconf
from . import utils

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'yandex_station'


async def async_setup(hass: HomeAssistantType, hass_config: dict):
    config: dict = hass_config[DOMAIN]

    filename = hass.config.path(f".{DOMAIN}.txt")

    if CONF_TOKEN in config:
        yandex_token = config[CONF_TOKEN]
    else:
        yandex_token = utils.load_token(filename)

    session = async_get_clientsession(hass)

    if not yandex_token:
        yandex_token = await utils.get_yandex_token(
            config[CONF_USERNAME], config[CONF_PASSWORD], session)
        utils.save_token(filename, yandex_token)

    if not yandex_token:
        _LOGGER.error("Yandex token not found.")
        return False

    devices = await utils.get_devices(yandex_token, session)

    _LOGGER.info(f"{len(devices)} device found in Yandex account.")

    if config.get('control_hdmi'):
        filename = hass.config.path(f".{DOMAIN}_cookies.pickle")
        quasar = utils.Quasar(config[CONF_USERNAME], config[CONF_PASSWORD],
                              filename)
        hass.data[DOMAIN] = quasar

    async def send_command(call: ServiceCall):
        data = dict(call.data)

        device = data.pop('device', None)
        entity_ids = data.pop(ATTR_ENTITY_ID, None) or \
                     utils.find_station(hass, device)

        _LOGGER.debug(f"Send command to: {entity_ids}")

        if not entity_ids:
            _LOGGER.error("Entity_id parameter required")
            return

        data = {
            ATTR_MEDIA_CONTENT_ID: json.dumps(data),
            ATTR_MEDIA_CONTENT_TYPE: 'command',
            ATTR_ENTITY_ID: entity_ids,
        }

        await hass.services.async_call(
            DOMAIN_MP, SERVICE_PLAY_MEDIA, data, blocking=True
        )

    async def yandex_station_say(call: ServiceCall):
        entity_ids = call.data.get(ATTR_ENTITY_ID) or utils.find_station(hass)

        _LOGGER.debug(f"Yandex say to: {entity_ids}")

        if not entity_ids:
            _LOGGER.error("Entity_id parameter required")
            return

        message = call.data.get(ATTR_MESSAGE)

        data = {
            ATTR_MEDIA_CONTENT_ID: message,
            ATTR_MEDIA_CONTENT_TYPE: 'tts',
            ATTR_ENTITY_ID: entity_ids,
        }

        await hass.services.async_call(
            DOMAIN_MP, SERVICE_PLAY_MEDIA, data, blocking=True
        )

    def add_device(info: dict):
        info['yandex_token'] = yandex_token
        hass.async_create_task(discovery.async_load_platform(
            hass, DOMAIN_MP, DOMAIN, info, hass_config))

    hass.services.async_register(DOMAIN, 'send_command', send_command)

    if DOMAIN_TTS not in hass_config:
        # need init tts service to show in media_player window
        await async_setup_component(hass, DOMAIN_TTS, hass_config)

    service_name = config.get('tts_service_name', 'yandex_station_say')
    hass.services.async_register(DOMAIN_TTS, service_name, yandex_station_say)

    listener = YandexIOListener(devices)
    listener.listen(add_device)

    return True


class YandexIOListener:
    def __init__(self, devices: dict):
        self.devices = devices
        self._add_device = None

    def listen(self, add_device: Callable):
        self._add_device = add_device

        zeroconf = Zeroconf()
        ServiceBrowser(zeroconf, '_yandexio._tcp.local.', listener=self)

    def add_service(self, zeroconf: Zeroconf, type_: str, name: str):
        """Стандартная функция ServiceBrowser."""
        _LOGGER.debug(f"Add service {name}")

        info = zeroconf.get_service_info(type_, name)

        properties = {
            k.decode(): v.decode() if isinstance(v, bytes) else v
            for k, v in info.properties.items()
        }

        _LOGGER.debug(f"Properties: {properties}")

        deviceid = properties['deviceId']

        device = next((p for p in self.devices if p['id'] == deviceid), None)
        if device:
            _LOGGER.info(f"Found Yandex device {deviceid}")

            device['host'] = str(ipaddress.ip_address(info.address))
            device['port'] = info.port

            self._add_device(device)
        else:
            _LOGGER.warning(f"Device {deviceid} not found in Yandex account.")

    def remove_service(self, zeroconf: Zeroconf, type: str, name: str):
        _LOGGER.debug(f"Remove service {name}")
