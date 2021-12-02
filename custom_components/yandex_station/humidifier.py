"""Support for Yandex Smart Home humidifier."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate.const import SUPPORT_TARGET_HUMIDITY
from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.const import ATTR_STATE
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv

from . import CONF_INCLUDE, DATA_CONFIG, DOMAIN, YandexQuasar

_LOGGER = logging.getLogger(__name__)

SERVICE_MUTE = "mute"
SERVICE_IONIZATION = "ionization"
SERVICE_BACKLIGHT = "backlight"

HUMIDIFIER_STATE_USER_SCHEMA = {vol.Required(ATTR_STATE): cv.boolean}


DEVICES = ["devices.types.humidifier"]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up humidifier from a config entry."""
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]
    devices = [
        YandexHumidifier(quasar, device)
        for device in quasar.devices
        if device["name"] in include and device["type"] in DEVICES
    ]

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_MUTE, HUMIDIFIER_STATE_USER_SCHEMA, "mute"
    )
    platform.async_register_entity_service(
        SERVICE_IONIZATION, HUMIDIFIER_STATE_USER_SCHEMA, "ionization"
    )
    platform.async_register_entity_service(
        SERVICE_BACKLIGHT, HUMIDIFIER_STATE_USER_SCHEMA, "backlight"
    )

    async_add_entities(devices, True)


# noinspection PyAbstractClass
class YandexHumidifier(HumidifierEntity):
    """Yandex Home humidifier entity"""
    _is_on = None
    _min_humidity = None
    _max_humidity = None
    _target_humidity = None
    _precision = None
    _is_muted = None
    _is_ionization_on = None
    _is_backlight_on = None
    _supported = 0

    def __init__(self, quasar: YandexQuasar, device: dict) -> None:
        """Initialize entity."""
        self.quasar = quasar
        self.device = device

    @property
    def unique_id(self):
        """Return entity unique id."""
        return self.device["id"].replace("-", "")

    @property
    def name(self):
        """Return entity name."""
        return self.device["name"]

    @property
    def is_on(self) -> bool:
        """Return if device is turned on."""
        return self._is_on

    @property
    def min_humidity(self) -> int:
        """Return min humidity."""
        return self._min_humidity

    @property
    def max_humidity(self) -> int:
        """Return max humidity."""
        return self._max_humidity

    @property
    def precision(self) -> int:
        """Return target humidity precision."""
        return self._precision

    @property
    def target_humidity(self) -> int:
        """Return target humidity."""
        return self._target_humidity

    @property
    def is_muted(self) -> bool:
        """Return if device is muted."""
        return self._is_muted

    @property
    def is_ionization_on(self) -> bool:
        """Return if ionization is turned on."""
        return self._is_ionization_on

    @property
    def is_backlight_on(self) -> bool:
        """Return if backlight is turned on."""
        return self._is_backlight_on

    @property
    def supported_features(self):
        """Return supported features."""
        return self._supported

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device specific state attributes."""
        attributes = {
            "is_muted": self.is_muted,
            "is_ionization_on": self.is_ionization_on,
            "is_backlight_on": self.is_backlight_on,
        }
        return attributes

    async def init_params(self, capabilities: dict):
        """Initialize parameters."""
        for capability in capabilities:
            parameters = capability["parameters"]
            instance = parameters.get("instance")
            if instance == "humidity":
                self._supported |= SUPPORT_TARGET_HUMIDITY
                range_ = parameters["range"]
                self._min_humidity = range_["min"]
                self._max_humidity = range_["max"]
                self._precision = range_["precision"]

    async def async_update(self):
        """Update the entity."""
        data = await self.quasar.get_device(self.device["id"])
        if self._is_on is None:
            await self.init_params(data["capabilities"])

        for capability in data["capabilities"]:
            if not capability["retrievable"]:
                continue
            instance = capability["state"]["instance"]
            value = capability["state"]["value"]
            if instance == "on":
                self._is_on = value
            if instance == "humidity":
                self._target_humidity = value
            if instance == "mute":
                self._is_muted = value
            if instance == "ionization":
                self._is_ionization_on = value
            if instance == "backlight":
                self._is_backlight_on = value

    async def async_turn_on(self, **kwargs):
        """Turn on."""
        await self.quasar.device_action(self.device["id"], on=True)

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        await self.quasar.device_action(self.device["id"], on=False)

    async def async_set_humidity(self, humidity):
        """Set humidity."""
        await self.quasar.device_action(self.device["id"], humidity=humidity)

    async def mute(self, state):
        """Mute humidifier."""
        await self.quasar.device_action(self.device["id"], mute=state)

    async def ionization(self, state):
        """Turn on/off ionization."""
        await self.quasar.device_action(self.device["id"], ionization=state)

    async def backlight(self, state):
        """Turn on/off backlight."""
        await self.quasar.device_action(self.device["id"], backlight=state)
