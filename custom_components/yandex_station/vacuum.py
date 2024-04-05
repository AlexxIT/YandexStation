import logging

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.const import STATE_IDLE, STATE_PAUSED

from .core.entity import YandexEntity
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = ("devices.types.vacuum_cleaner",)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        YandexVacuum(quasar, device, config)
        for quasar, device, config in hass_utils.incluce_devices(hass, entry)
        if device["type"] in INCLUDE_TYPES
    )


# noinspection PyAbstractClass
class YandexVacuum(StateVacuumEntity, YandexEntity):
    pause_value: bool = None
    on_value: bool = None

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
        if "pause" in capabilities:
            self.pause_value = capabilities["pause"]

        if "on" in capabilities:
            self.on_value = capabilities["on"]

        if "battery_level" in properties:
            self._attr_battery_level = properties["battery_level"]

        if "work_speed" in capabilities:
            self._attr_fan_speed = capabilities["work_speed"]

        if self.pause_value:
            self._attr_state = STATE_PAUSED
        elif self.on_value:
            self._attr_state = STATE_CLEANING
        else:
            self._attr_state = STATE_IDLE

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
