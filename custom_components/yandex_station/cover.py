import logging

from homeassistant.components.cover import CoverEntity, CoverEntityFeature

from .core.entity import YandexEntity
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = ("devices.types.openable.curtain",)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        YandexCover(quasar, device, config)
        for quasar, device, config in hass_utils.incluce_devices(hass, entry)
        if device["type"] in INCLUDE_TYPES
    )


# noinspection PyAbstractClass
class YandexCover(CoverEntity, YandexEntity):
    _attr_is_closed = None
    _attr_supported_features = 0

    def internal_init(self, capabilities: dict, properties: dict):
        if "on" in capabilities:
            self._attr_supported_features |= (
                CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
            )

        if "open" in capabilities:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

        if "pause" in capabilities:
            self._attr_supported_features |= CoverEntityFeature.STOP

    def internal_update(self, capabilities: dict, properties: dict):
        if (value := capabilities.get("on")) is not None:
            self._attr_is_closed = value is False

        if (value := capabilities.get("open")) is not None:
            self._attr_current_cover_position = value
            self._attr_is_closed = value == 0

    async def async_open_cover(self, **kwargs):
        await self.device_action("on", True)

    async def async_close_cover(self, **kwargs):
        await self.device_action("on", False)

    async def async_stop_cover(self, **kwargs):
        await self.device_action("pause", True)

    async def async_set_cover_position(self, position: int, **kwargs):
        await self.device_action("open", position)
