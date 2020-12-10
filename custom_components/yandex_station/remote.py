import asyncio
import logging
from typing import Iterable, Any

from homeassistant.components.remote import RemoteEntity, ATTR_DELAY_SECS, \
    ATTR_NUM_REPEATS

from . import DOMAIN, DATA_CONFIG, CONF_INCLUDE, YandexQuasar

_LOGGER = logging.getLogger(__name__)

DEVICES = ['devices.types.other']


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]
    devices = [
        YandexOther(quasar, device)
        for device in quasar.devices
        if device['name'] in include and device['type'] in DEVICES
    ]
    async_add_entities(devices, True)


# noinspection PyAbstractClass
class YandexOther(RemoteEntity):
    _name = None

    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device

        self.buttons = {}

    async def async_added_to_hass(self):
        self._name = self.device['name']

        data = await self.quasar.get_device(self.device['id'])
        for capability in data['capabilities']:
            if capability['type'] != 'devices.capabilities.custom.button':
                continue
            name = capability['parameters']['name']
            self.buttons[name] = capability['parameters']['instance']

    @property
    def unique_id(self):
        return self.device['id'].replace('-', '')

    @property
    def name(self):
        return self._name

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def is_on(self) -> bool:
        return True

    async def async_send_command(self, command: Iterable[str],
                                 **kwargs: Any) -> None:
        num_repeats = kwargs.get(ATTR_NUM_REPEATS)
        if num_repeats:
            command *= num_repeats

        delay = kwargs.get(ATTR_DELAY_SECS, 0)

        for i, cmd in enumerate(command):
            if cmd not in self.buttons:
                _LOGGER.error(f"Неизвестная команда {cmd}")
                continue

            if delay and i:
                await asyncio.sleep(delay)

            payload = {self.buttons[cmd]: True}
            await self.quasar.device_action(self.device['id'], **payload)
