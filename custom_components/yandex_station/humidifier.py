import logging

from homeassistant.components.humidifier import (
    HumidifierEntity,
    HumidifierEntityFeature,
)

from .core import utils
from .core.entity import YandexEntity
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = ("devices.types.humidifier",)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        YandexHumidifier(quasar, device, config)
        for quasar, device, config in hass_utils.incluce_devices(hass, entry)
        if device["type"] in INCLUDE_TYPES
    )


# noinspection PyAbstractClass
class YandexHumidifier(HumidifierEntity, YandexEntity):
    mode_instance: str = None

    def internal_init(self, capabilities: dict, properties: dict):
        candidates = ["fan_speed", "work_speed"]

        self.mode_instance = next((i for i in candidates if i in capabilities), None)

        if item := capabilities.get("humidity"):
            self._attr_min_humidity = item["range"]["min"]
            self._attr_max_humidity = item["range"]["max"]

        if item := capabilities.get(self.mode_instance):
            self._attr_supported_features |= HumidifierEntityFeature.MODES
            self._attr_available_modes = [i["value"] for i in item["modes"]]

    def internal_update(self, capabilities: dict, properties: dict):
        if "on" in capabilities:
            self._attr_is_on = capabilities["on"]

        if "humidity" in capabilities:
            self._attr_target_humidity = capabilities["humidity"]

        if self.mode_instance in capabilities:
            self._attr_mode = capabilities[self.mode_instance]

        if "humidity" in properties:
            self._attr_current_humidity = properties["humidity"]

    async def async_added_to_hass(self):
        if item := self.config.get("current_humidity"):
            on_remove = utils.track_template(self.hass, item, self.on_track_template)
            self.async_on_remove(on_remove)

    def on_track_template(self, value):
        try:
            self._attr_current_humidity = int(value)
        except:
            self._attr_current_humidity = None
        self._async_write_ha_state()

    async def async_set_humidity(self, humidity: int) -> None:
        await self.device_action("humidity", humidity)

    async def async_set_mode(self, mode: str) -> None:
        await self.device_action(self.mode_instance, mode)

    async def async_turn_on(self, **kwargs):
        await self.device_action("on", True)

    async def async_turn_off(self, **kwargs):
        await self.device_action("on", False)
