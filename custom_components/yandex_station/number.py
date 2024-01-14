import logging

from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_INCLUDE, UnitOfTemperature

from .core import utils
from .core.const import DATA_CONFIG, DOMAIN
from .core.entity import YandexCustomEntity

_LOGGER = logging.getLogger(__name__)

INCLUDE_CAPABILITIES = ["devices.capabilities.range"]

UNITS = {"unit.temperature.celsius": UnitOfTemperature.CELSIUS}


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]

    entities = []

    for device in quasar.devices:
        # compare device name/id/room/etc
        if not (config := utils.device_include(device, include)):
            continue

        if not (instances := config.get("capabilities")):
            continue

        for config in device["capabilities"]:
            if utils.instance_include(config, instances, INCLUDE_CAPABILITIES):
                entities.append(YandexCustomNumber(quasar, device, config))

    async_add_entities(entities, True)


# noinspection PyAbstractClass
class YandexCustomNumber(NumberEntity, YandexCustomEntity):
    def internal_init(self, capabilities: dict, properties: dict):
        if item := capabilities.get(self.instance):
            self._attr_native_max_value = item["range"]["max"]
            self._attr_native_min_value = item["range"]["min"]
            self._attr_native_step = item["range"]["precision"]
            self._attr_native_unit_of_measurement = UNITS.get(item["unit"])

    def internal_update(self, capabilities: dict, properties: dict):
        if self.instance in capabilities:
            self._attr_native_value = capabilities[self.instance]

    async def async_set_native_value(self, value: float) -> None:
        await self.quasar.device_action(self.device["id"], self.instance, value)
