import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
)

from .core.entity import YandexCustomEntity
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

# https://yandex.ru/dev/dialogs/smart-home/doc/concepts/device-type-sensor.html
INCLUDE_TYPES = (
    "devices.types.sensor",
    "devices.types.sensor.button",
    "devices.types.sensor.climate",
    "devices.types.sensor.gas",
    "devices.types.sensor.illumination",
    "devices.types.sensor.motion",
    "devices.types.sensor.open",
    "devices.types.sensor.smoke",
    "devices.types.sensor.vibration",
    "devices.types.sensor.water_leak",
    "devices.types.smart_meter",
    "devices.types.smart_meter.cold_water",
    "devices.types.smart_meter.electricity",
    "devices.types.smart_meter.gas",
    "devices.types.smart_meter.heat",
    "devices.types.smart_meter.hot_water",
    "devices.types.smart_speaker.yandex.station.plum",
    "devices.types.socket",
)
INCLUDE_PROPERTIES = ("devices.properties.float", "devices.properties.event")

SENSOR = SensorDeviceClass  # just to reduce the code

ENTITY_DESCRIPTIONS: dict[str, dict] = {
    "temperature": {"class": SENSOR.TEMPERATURE, "units": UnitOfTemperature.CELSIUS},
    "humidity": {"class": SENSOR.HUMIDITY, "units": PERCENTAGE},
    "pm2.5_density": {
        "class": SENSOR.PM25,
        "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    "pm10_density": {
        "class": SENSOR.PM10,
        "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    "co2_level": {"class": SENSOR.CO2, "units": CONCENTRATION_PARTS_PER_MILLION},
    "illumination": {"class": SENSOR.ILLUMINANCE, "units": LIGHT_LUX},
    "battery_level": {"class": SENSOR.BATTERY, "units": PERCENTAGE},
    "pressure": {"class": SENSOR.PRESSURE, "units": UnitOfPressure.MMHG},
    "voltage": {"class": SENSOR.VOLTAGE, "units": UnitOfElectricPotential.VOLT},
    "power": {"class": SENSOR.POWER, "units": UnitOfPower.WATT},
    "amperage": {"class": SENSOR.CURRENT, "units": UnitOfElectricCurrent.AMPERE},
    "vibration": {"class": SENSOR.ENUM},
    "open": {"class": SENSOR.ENUM},
    "button": {"class": SENSOR.ENUM},
    "motion": {"class": SENSOR.ENUM},
    "smoke": {"class": SENSOR.ENUM},
    "gas": {"class": SENSOR.ENUM},
    "food_level": {"class": SENSOR.ENUM},
    "water_level": {"class": SENSOR.ENUM},
    "water_leak": {"class": SENSOR.ENUM},
    "electricity_meter": {"class": SENSOR.ENERGY, "units": UnitOfEnergy.KILO_WATT_HOUR},
    "gas_meter": {"class": SENSOR.GAS, "units": UnitOfVolume.CUBIC_METERS},
    "water_meter": {"class": SENSOR.WATER, "units": UnitOfVolume.CUBIC_METERS},
}


async def async_setup_entry(hass, entry, async_add_entities):
    entities = []

    for quasar, device, config in hass_utils.incluce_devices(hass, entry):
        if "properties" in config:
            instances = config["properties"]
        elif device["type"] in INCLUDE_TYPES:
            instances = ENTITY_DESCRIPTIONS.keys()  # all supported instances
        else:
            continue

        for instance in device["properties"]:
            if instance["type"] not in INCLUDE_PROPERTIES:
                continue
            if instance["parameters"]["instance"] in instances:
                entities.append(YandexCustomSensor(quasar, device, instance))

    async_add_entities(entities)


# noinspection PyAbstractClass
class YandexCustomSensor(SensorEntity, YandexCustomEntity):
    def internal_init(self, capabilities: dict, properties: dict):
        if desc := ENTITY_DESCRIPTIONS.get(self.instance):
            self._attr_device_class = desc["class"]
            if "units" in desc:
                self._attr_native_unit_of_measurement = desc["units"]
                self._attr_state_class = SensorStateClass.MEASUREMENT

    def internal_update(self, capabilities: dict, properties: dict):
        if self.instance in properties:
            self._attr_native_value = properties[self.instance]
