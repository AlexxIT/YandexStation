import logging

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.const import STATE_IDLE, STATE_PAUSED

from . import CONF_INCLUDE, DATA_CONFIG, DOMAIN
from .core import utils
from .core.entity import YandexEntity

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = ["devices.types.vacuum_cleaner"]


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]
    entities = [
        YandexVacuum(quasar, device)
        for device in quasar.devices
        if utils.device_include(device, include, INCLUDE_TYPES)
    ]
    async_add_entities(entities)


# noinspection PyAbstractClass
class YandexVacuum(StateVacuumEntity, YandexEntity):
    def internal_init(self, capabilities: dict, properties: dict):
        if "on" in capabilities:
            self._attr_supported_features |= (
                VacuumEntityFeature.START
                | VacuumEntityFeature.STOP
                | VacuumEntityFeature.RETURN_HOME
            )

        if "pause" in capabilities:
            self._attr_supported_features |= VacuumEntityFeature.PAUSE

        if item := capabilities.get("work_speed"):
            self._attr_supported_features |= VacuumEntityFeature.FAN_SPEED
            self._attr_fan_speed_list = [p["value"] for p in item["modes"]]

        if "battery_level" in properties:
            self._attr_supported_features |= VacuumEntityFeature.BATTERY

    def internal_update(self, capabilities: dict, properties: dict):
        if capabilities.get("pause"):
            self._attr_state = STATE_PAUSED
        elif capabilities.get("on"):
            self._attr_state = STATE_CLEANING
        else:
            self._attr_state = STATE_IDLE

        self._attr_battery_level = properties.get("battery_level")
        self._attr_fan_speed = capabilities.get("work_speed")

    async def async_start(self):
        await self.quasar.device_action(self.device["id"], "on", True)

    async def async_stop(self, **kwargs):
        await self.quasar.device_action(self.device["id"], "on", False)

    async def async_pause(self):
        await self.quasar.device_action(self.device["id"], "pause", True)

    async def async_return_to_base(self, **kwargs):
        await self.async_stop()

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        await self.quasar.device_action(self.device["id"], "work_speed", fan_speed)
