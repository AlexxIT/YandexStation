import ipaddress
import logging
from typing import Callable

from homeassistant.components.media_player import DOMAIN as DOMAIN_MP
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import ServiceCall
from homeassistant.helpers.discovery import load_platform

from zeroconf import ServiceBrowser, Zeroconf
from . import utils

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'yandex_station'


def setup(hass, hass_config):
    config = hass_config[DOMAIN]

    filename = hass.config.path(f".{DOMAIN}.txt")

    if CONF_TOKEN in config:
        yandex_token = config[CONF_TOKEN]
    else:
        yandex_token = utils.load_token(filename)

    if not yandex_token:
        yandex_token = utils.get_yandex_token(config[CONF_USERNAME],
                                              config[CONF_PASSWORD])
        utils.save_token(filename, yandex_token)

    if not yandex_token:
        _LOGGER.error("Yandex token not found.")
        return False

    devices = utils.get_devices(yandex_token)

    _LOGGER.info(f"{len(devices)} device found in Yandex account.")

    async def play_media(call: ServiceCall):
        data = dict(call.data)

        device: dict = data.pop('device', None)
        if device:
            # Search device by id or name
            device = next((p for p in devices
                           if p['id'] == device or p['name'] == device), None)
        elif len(devices):
            # Take first device with host in account
            device = next((p for p in devices if 'host' in p), None)

        if device:
            if 'host' in data:
                # Set host from service data
                device = device.copy()
                device['host'] = data.pop('host')
                device['port'] = data.pop('port', 1961)

            if 'host' in device:
                await utils.send_to_station(device, data)
            else:
                _LOGGER.error(f"Unknown host for device {device['id']}")

        else:
            _LOGGER.error(f"Not found device with host in Yandex")

    def add_device(info: dict):
        info['yandex_token'] = yandex_token
        load_platform(hass, DOMAIN_MP, DOMAIN, info, hass_config)

    hass.services.register(DOMAIN, 'send_command', play_media)

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
