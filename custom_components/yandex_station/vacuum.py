import logging

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature

from .core.entity import YandexEntity
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = ("devices.types.vacuum_cleaner",)


try:
    # https://developers.home-assistant.io/blog/2024/12/08/new-vacuum-state-property/
    from homeassistant.components.vacuum import VacuumActivity

    class VacuumBase(StateVacuumEntity):
        def set_cleaning_state(self):
            self._attr_activity = VacuumActivity.CLEANING

        def set_idle_state(self):
            self._attr_activity = VacuumActivity.IDLE

        def set_paused_state(self):
            self._attr_activity = VacuumActivity.PAUSED

except ImportError:
    from homeassistant.components.vacuum import STATE_CLEANING
    from homeassistant.const import STATE_IDLE, STATE_PAUSED

    class VacuumBase(StateVacuumEntity):
        def set_cleaning_state(self):
            self._attr_state = STATE_CLEANING

        def set_idle_state(self):
            self._attr_state = STATE_IDLE

        def set_paused_state(self):
            self._attr_state = STATE_PAUSED


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        YandexVacuum(quasar, device, config)
        for quasar, device, config in hass_utils.incluce_devices(hass, entry)
        if device["type"] in INCLUDE_TYPES
    )


# noinspection PyAbstractClass
class YandexVacuum(VacuumBase, YandexEntity):
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
            self.set_paused_state()
        elif self.on_value:
            self.set_cleaning_state()
        else:
            self.set_idle_state()

    async def async_start(self):
        await self.device_action("on", True)

    async def async_stop(self, **kwargs):
        await self.device_action("on", False)

    async def async_pause(self):
        await self.device_action("pause", True)

    async def async_return_to_base(self, **kwargs):
        await self.async_stop()

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        await self.device_action("work_speed", fan_speed)
