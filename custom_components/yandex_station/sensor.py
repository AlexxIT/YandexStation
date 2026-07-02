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
    UnitOfLength,
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
    "devices.types.sensor.presence",
    "devices.types.sensor.smoke",
    "devices.types.sensor.vibration",
    "devices.types.sensor.water_leak",
    "devices.types.smart_meter",
    "devices.types.smart_meter.cold_water",
    "devices.types.smart_meter.electricity",
    "devices.types.smart_meter.gas",
    "devices.types.smart_meter.heat",
    "devices.types.smart_meter.hot_water",
    "devices.types.socket",
    "devices.types.remote_car",  # fuel_level, petrol_mileage
    "devices.types.remote.ir",  # temperature, humidity
    "devices.types.smart_speaker.yandex.station.pickle",  # co2_level, temp., hum.
    "devices.types.smart_speaker.yandex.station.plum",  # battery
    "devices.types.vacuum_cleaner",  # battery_level
)
INCLUDE_PROPERTIES = ("devices.properties.float", "devices.properties.event")

SENSOR = SensorDeviceClass  # just to reduce the code

ENTITY_DESCRIPTIONS: dict[str, dict] = {
    "temperature": {
        "class": SENSOR.TEMPERATURE,
        "state": SensorStateClass.MEASUREMENT,
        "units": UnitOfTemperature.CELSIUS,
    },
    "humidity": {
        "class": SENSOR.HUMIDITY,
        "state": SensorStateClass.MEASUREMENT,
        "units": PERCENTAGE,
    },
    "pm2.5_density": {
        "class": SENSOR.PM25,
        "state": SensorStateClass.MEASUREMENT,
        "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    "pm10_density": {
        "class": SENSOR.PM10,
        "state": SensorStateClass.MEASUREMENT,
        "units": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    },
    "co2_level": {
        "class": SENSOR.CO2,
        "state": SensorStateClass.MEASUREMENT,
        "units": CONCENTRATION_PARTS_PER_MILLION,
    },
    "illumination": {
        "class": SENSOR.ILLUMINANCE,
        "state": SensorStateClass.MEASUREMENT,
        "units": LIGHT_LUX,
    },
    "battery_level": {
        "class": SENSOR.BATTERY,
        "state": SensorStateClass.MEASUREMENT,
        "units": PERCENTAGE,
    },
    "pressure": {
        "class": SENSOR.PRESSURE,
        "state": SensorStateClass.MEASUREMENT,
        "units": UnitOfPressure.MMHG,
    },
    "voltage": {
        "class": SENSOR.VOLTAGE,
        "state": SensorStateClass.MEASUREMENT,
        "units": UnitOfElectricPotential.VOLT,
    },
    "power": {
        "class": SENSOR.POWER,
        "state": SensorStateClass.MEASUREMENT,
        "units": UnitOfPower.WATT,
    },
    "amperage": {
        "class": SENSOR.CURRENT,
        "state": SensorStateClass.MEASUREMENT,
        "units": UnitOfElectricCurrent.AMPERE,
    },
    "vibration": {"class": SENSOR.ENUM},
    "open": {"class": SENSOR.ENUM},
    "button": {"class": SENSOR.ENUM},
    "motion": {"class": SENSOR.ENUM},
    "occupancy": {"units": "objects"},
    "smoke": {"class": SENSOR.ENUM},
    "gas": {"class": SENSOR.ENUM},
    "food_level": {"class": SENSOR.ENUM},
    "water_level": {"class": SENSOR.ENUM},
    "water_leak": {"class": SENSOR.ENUM},
    "electricity_meter": {
        "class": SENSOR.ENERGY,
        "state": SensorStateClass.TOTAL,
        "units": UnitOfEnergy.KILO_WATT_HOUR,
    },
    "gas_meter": {
        "class": SENSOR.GAS,
        "state": SensorStateClass.TOTAL,
        "units": UnitOfVolume.CUBIC_METERS,
    },
    "water_meter": {
        "class": SENSOR.WATER,
        "state": SensorStateClass.TOTAL,
        "units": UnitOfVolume.CUBIC_METERS,
    },
    # there is no better option than a battery for fuel_level
    "fuel_level": {
        "class": SENSOR.BATTERY,
        "state": SensorStateClass.MEASUREMENT,
        "units": PERCENTAGE,
    },
    "petrol_mileage": {
        "class": SENSOR.DISTANCE,
        "state": SensorStateClass.MEASUREMENT,
        "units": UnitOfLength.KILOMETERS,
    },
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
            if "class" in desc:
                self._attr_device_class = desc["class"]
            if "state" in desc:
                self._attr_state_class = desc["state"]
            if "units" in desc:
                self._attr_native_unit_of_measurement = desc["units"]
        try:
            if self.config["parameters"]["range"]["precision"] == 1:
                self._attr_suggested_display_precision = 0
        except KeyError:
            pass

    def internal_update(self, capabilities: dict, properties: dict):
        if self.instance in properties:
            self._attr_native_value = properties[self.instance]
