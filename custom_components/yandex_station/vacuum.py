import logging

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    STATE_CLEANING,
    SUPPORT_START,
    SUPPORT_STOP,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_FAN_SPEED,
    SUPPORT_BATTERY,
)
from homeassistant.const import STATE_IDLE, STATE_PAUSED

from . import DOMAIN, CONF_INCLUDE, DATA_CONFIG, YandexQuasar

_LOGGER = logging.getLogger(__name__)

DEVICES = ["devices.types.vacuum_cleaner"]


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]
    devices = [
        YandexVacuum(quasar, device)
        for device in quasar.devices
        if device["name"] in include and device["type"] in DEVICES
    ]
    async_add_entities(devices)


# noinspection PyAbstractClass
class VacuumBase(StateVacuumEntity):
    _attr_state: str = None

    _attr_battery_level: int = None
    _attr_fan_speed: str = None
    _attr_fan_speed_list: list[str] = None
    _attr_supported_features: int = 0

    @property
    def state(self):
        return self._attr_state

    @property
    def supported_features(self):
        return self._attr_supported_features

    @property
    def battery_level(self):
        return self._attr_battery_level

    @property
    def fan_speed(self):
        return self._attr_fan_speed

    @property
    def fan_speed_list(self):
        return self._attr_fan_speed_list


# noinspection PyAbstractClass
class YandexVacuum(VacuumBase):
    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device

    @property
    def unique_id(self):
        return self.device["id"].replace("-", "")

    @property
    def name(self):
        return self.device["name"]

    @property
    def should_poll(self):
        return True

    async def async_start(self):
        await self.quasar.device_action(self.device["id"], on=True)

    async def async_stop(self, **kwargs):
        await self.quasar.device_action(self.device["id"], on=False)

    async def async_pause(self):
        await self.quasar.device_action(self.device["id"], pause=True)

    async def async_return_to_base(self, **kwargs):
        await self.async_stop()

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        await self.quasar.device_action(self.device["id"], work_speed=fan_speed)

    async def async_added_to_hass(self):
        data = await self.quasar.get_device(self.device["id"])

        for capability in data["capabilities"]:
            # TODO: type devices.capabilities.on_off don't have property
            #  parameters instance
            instance = capability["parameters"].get("instance", "on")
            if instance == "on":
                self._attr_supported_features |= (
                    SUPPORT_START | SUPPORT_STOP | SUPPORT_RETURN_HOME
                )

            elif instance == "work_speed":
                self._attr_supported_features |= SUPPORT_FAN_SPEED
                self._attr_fan_speed_list = [
                    p["value"] for p in capability["parameters"]["modes"]
                ]

            elif instance == "pause":
                self._attr_supported_features |= SUPPORT_PAUSE

        for property_ in data["properties"]:
            instance = property_["parameters"]["instance"]
            if instance == "battery_level":
                self._attr_supported_features |= SUPPORT_BATTERY

        await self.async_update(data)

    async def async_update(self, data: dict = None):
        if not data:
            data = await self.quasar.get_device(self.device["id"])

        self._attr_available = data["state"] == "online"

        for capability in data["capabilities"]:
            if not capability["retrievable"]:
                continue

            instance = capability["state"]["instance"]
            if instance == "on":
                self._attr_state = (
                    STATE_CLEANING if capability["state"]["value"] else STATE_IDLE
                )
            elif instance == "work_speed":
                self._attr_fan_speed = capability["state"]["value"]
            elif instance == "pause":
                if capability["state"]["value"]:
                    self._attr_state = STATE_PAUSED

        for property_ in data["properties"]:
            instance = property_["parameters"]["instance"]
            if instance == "battery_level":
                self._attr_battery_level = property_["state"]["value"]
