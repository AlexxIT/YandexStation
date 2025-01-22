import logging

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature

from .core.entity import YandexEntity
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = ("devices.types.cooking.kettle",)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        YandexKettle(quasar, device, config)
        for quasar, device, config in hass_utils.incluce_devices(hass, entry)
        if device["type"] in INCLUDE_TYPES
    )


# noinspection PyAbstractClass
class YandexKettle(WaterHeaterEntity, YandexEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "kettle"

    def internal_init(self, capabilities: dict, properties: dict):
        self._attr_operation_list = ["on", "off"] if "on" in capabilities else []

        if item := capabilities.get("tea_mode"):
            self._attr_operation_list += [i["value"] for i in item["modes"]]

        if self._attr_operation_list:
            self._attr_supported_features |= WaterHeaterEntityFeature.OPERATION_MODE

        if item := capabilities.get("temperature"):
            self._attr_supported_features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
            self._attr_min_temp = item["range"]["min"]
            self._attr_max_temp = item["range"]["max"]

    def internal_update(self, capabilities: dict, properties: dict):
        if "on" in capabilities:
            self._attr_current_operation = "on" if capabilities["on"] else "off"
        if "temperature" in capabilities:
            self._attr_target_temperature = capabilities["temperature"]
        if "temperature" in properties:
            self._attr_current_temperature = properties["temperature"]

    async def async_set_operation_mode(self, operation_mode):
        if operation_mode == "on":
            await self.device_action("on", True)
        elif operation_mode == "off":
            await self.device_action("on", False)
        else:
            await self.device_action("tea_mode", operation_mode)

    async def async_set_temperature(self, temperature: float, **kwargs):
        await self.device_action("temperature", temperature)

    async def async_turn_on(self):
        await self.device_action("on", True)

    async def async_turn_off(self):
        await self.device_action("on", False)
