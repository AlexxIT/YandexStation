import asyncio
import logging

from homeassistant.components.remote import RemoteEntity

from .core.entity import YandexEntity
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = ("devices.types.other",)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        YandexOther(quasar, device, config)
        for quasar, device, config in hass_utils.incluce_devices(hass, entry)
        if device["type"] in INCLUDE_TYPES
    )


# noinspection PyAbstractClass
class YandexOther(RemoteEntity, YandexEntity):
    buttons: dict[str, str]

    def internal_init(self, capabilities: dict, properties: dict):
        self.buttons = {}
        for capability in capabilities.values():
            instance: str = capability["instance"]
            if instance.isdecimal():
                self.buttons[capability["name"]] = instance

    async def async_send_command(
        self,
        command: list[str],
        num_repeats: int = None,
        delay_secs: float = None,
        **kwargs,
    ) -> None:
        if num_repeats:
            command *= num_repeats

        for i, cmd in enumerate(command):
            if cmd not in self.buttons:
                _LOGGER.warning(f"Неизвестная команда {cmd}")
                continue

            if delay_secs and i:
                await asyncio.sleep(delay_secs)

            payload = {self.buttons[cmd]: True}
            await self.device_actions(**payload)
