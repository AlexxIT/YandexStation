import logging

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import CONF_INCLUDE, UnitOfTemperature

from .core import utils
from .core.const import DATA_CONFIG, DOMAIN
from .core.entity import YandexEntity

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = ["devices.types.cooking.kettle"]


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]
    entities = [
        YandexKettle(quasar, device)
        for device in quasar.devices
        if utils.device_include(device, include, INCLUDE_TYPES)
    ]
    async_add_entities(entities, True)


# noinspection PyAbstractClass
class YandexKettle(WaterHeaterEntity, YandexEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def internal_init(self, capabilities: dict, properties: dict):
        self._attr_operation_list = ["on", "off"] if "on" in capabilities else []

        if item := capabilities.get("tea_mode"):
            self._attr_supported_features |= WaterHeaterEntityFeature.OPERATION_MODE
            self._attr_operation_list += [i["value"] for i in item["modes"]]

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
            await self.quasar.device_action(self.device["id"], "on", True)
        elif operation_mode == "off":
            await self.quasar.device_action(self.device["id"], "on", False)
        else:
            await self.quasar.device_action(
                self.device["id"], "tea_mode", operation_mode
            )

    async def async_set_temperature(self, temperature: float, **kwargs):
        await self.quasar.device_action(self.device["id"], "temperature", temperature)

    async def async_turn_on(self):
        await self.quasar.device_action(self.device["id"], "on", True)

    async def async_turn_off(self):
        await self.quasar.device_action(self.device["id"], "on", False)
