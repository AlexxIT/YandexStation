"""Support for Yandex Smart Home sensor."""
from __future__ import annotations

import logging
from typing import Any

from . import CONF_INCLUDE
from . import DATA_CONFIG
from . import DOMAIN
from . import YandexQuasar
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.const import PERCENTAGE
from homeassistant.const import TEMP_CELSIUS

_LOGGER = logging.getLogger(__name__)

DEVICES = ["devices.types.humidifier"]

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensor from a config entry."""
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]

    devices = []
    for device in quasar.devices:
        if device["name"] in include and device["type"] in DEVICES:
            data = await quasar.get_device(device["id"])
            for prop in data["properties"]:
                for description in SENSOR_TYPES:
                    if prop["parameters"]["instance"] == description.key:
                        devices.append(
                            YandexSensor(
                                quasar,
                                device,
                                prop["parameters"]["name"],
                                description,
                            )
                        )

    async_add_entities(devices, True)


# noinspection PyAbstractClass
class YandexSensor(SensorEntity):
    """Yandex Home sensor entity"""

    _humidity = None
    _temperature = None

    def __init__(
        self,
        quasar: YandexQuasar,
        device: dict,
        name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize entity."""
        self.quasar = quasar
        self.device = device
        self.sensor_name = name
        self.entity_description = description

    @property
    def unique_id(self):
        """Return entity unique id."""
        return f"{self.device['id'].replace('-', '')}: {self.entity_description.name}"

    @property
    def name(self):
        """Return entity name."""
        return f"{self.device['name']}: {self.sensor_name}"

    @property
    def humidity(self) -> int:
        """Return current humidity."""
        return self._humidity

    @property
    def temperature(self) -> int:
        """Return current temperature."""
        return self._temperature

    async def async_update(self):
        """Update the entity."""
        data = await self.quasar.get_device(self.device["id"])
        for prop in data["properties"]:
            instance = prop["parameters"]["instance"]
            if instance == "humidity":
                self._humidity = prop["state"]["value"]
            if instance == "temperature":
                self._temperature = prop["state"]["value"]

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        return getattr(self, self.entity_description.key)
