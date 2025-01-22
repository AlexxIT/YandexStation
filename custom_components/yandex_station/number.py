import logging

from homeassistant.components.number import NumberEntity
from homeassistant.const import UnitOfTemperature

from .core.entity import YandexCustomEntity
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

INCLUDE_CAPABILITIES = ("devices.capabilities.range",)

UNITS = {"unit.temperature.celsius": UnitOfTemperature.CELSIUS}


async def async_setup_entry(hass, entry, async_add_entities):
    entities = []

    for quasar, device, config in hass_utils.incluce_devices(hass, entry):
        if instances := config.get("capabilities"):
            for instance in device["capabilities"]:
                if instance["type"] not in INCLUDE_CAPABILITIES:
                    continue
                if instance["parameters"].get("instance", "on") in instances:
                    entities.append(YandexCustomNumber(quasar, device, instance))

    async_add_entities(entities)


# noinspection PyAbstractClass
class YandexCustomNumber(NumberEntity, YandexCustomEntity):
    def internal_init(self, capabilities: dict, properties: dict):
        if item := capabilities.get(self.instance):
            if range_ := item.get("range"):
                self._attr_native_max_value = range_["max"]
                self._attr_native_min_value = range_["min"]
                self._attr_native_step = range_["precision"]
            self._attr_native_unit_of_measurement = UNITS.get(item["unit"])

    def internal_update(self, capabilities: dict, properties: dict):
        if self.instance in capabilities:
            self._attr_native_value = capabilities[self.instance]

    async def async_set_native_value(self, value: float) -> None:
        await self.device_action(self.instance, value)
