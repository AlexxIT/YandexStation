"""Support for Yandex Smart Home sensor."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS, LIGHT_LUX, PRESSURE_MMHG

from . import DOMAIN, CONF_INCLUDE, DATA_CONFIG, YandexQuasar

_LOGGER = logging.getLogger(__name__)

DEVICES = ["devices.types.humidifier", "devices.types.sensor"]

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="illumination",
        name="Illumination",
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(key="open", name="Open"),
    SensorEntityDescription(
        key="battery_level",
        name="Battery Level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_MMHG,
        state_class=SensorStateClass.MEASUREMENT,
    )
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensor from a config entry."""
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]

    devices = []
    for device in quasar.devices:
        if device["name"] in include:
            for item in DEVICES:
                if device["type"].startswith(item):
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
        self.entity_description = description

        self._attr_name = f"{self.device['name']}: {name}"
        self._attr_unique_id = (
            f"{self.device['id'].replace('-', '')}: {self.entity_description.name}"
        )

    async def async_update(self):
        """Update the entity."""
        data = await self.quasar.get_device(self.device["id"])

        self._attr_available = data["state"] == "online"

        for prop in data["properties"]:
            if self.entity_description.key == prop["parameters"]["instance"]:
                self._attr_native_value = prop["state"]["value"]
