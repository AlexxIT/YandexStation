import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import CONF_INCLUDE, UnitOfTemperature

from .core import utils
from .core.const import DATA_CONFIG, DOMAIN
from .core.entity import YandexEntity
from .core.yandex_quasar import YandexQuasar

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = [
    "devices.types.purifier",
    "devices.types.thermostat",
    "devices.types.thermostat.ac",
]


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]
    entities = [
        YandexClimate(quasar, device, config)
        for device in quasar.devices
        if (config := utils.device_include(device, include, INCLUDE_TYPES))
    ]
    async_add_entities(entities, True)


def check_hvac_modes(item: dict) -> bool:
    try:
        return all(HVACMode(i["value"]) for i in item["modes"])
    except ValueError:
        return False


class YandexClimate(ClimateEntity, YandexEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    hvac_instance: str = None  # thermostat or program
    preset_instance: str = None
    on_value: bool = None
    hvac_value: str = None

    def internal_init(self, capabilities: dict, properties: dict):
        # instance candidates for hvac and preset modes
        candidates = ["thermostat", "program", "heat", "work_speed"]

        # 1. Select instance for hvac_mode
        for instance in candidates:
            if (item := capabilities.get(instance)) and check_hvac_modes(item):
                self.hvac_instance = instance
                candidates.remove(instance)
                break

        # 2. Select instance for preset_mode
        for instance in candidates:
            if instance in capabilities:
                self.preset_instance = instance
                break

        if item := capabilities.get(self.hvac_instance):
            self._attr_hvac_modes = [HVACMode(i["value"]) for i in item["modes"]]
        elif self.device["type"] == "devices.types.purifier":
            self._attr_hvac_modes = [HVACMode.FAN_ONLY]
        elif "heat" in capabilities:
            self._attr_hvac_modes = [HVACMode.HEAT]
        else:
            self._attr_hvac_modes = [HVACMode.AUTO]

        if "on" in capabilities:
            self._attr_hvac_modes += [HVACMode.OFF]

        if item := capabilities.get(self.preset_instance):
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = [i["value"] for i in item["modes"]]

        if item := capabilities.get("temperature"):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_min_temp = item["range"]["min"]
            self._attr_max_temp = item["range"]["max"]
            self._attr_target_temperature_step = item["range"]["precision"]

        if item := capabilities.get("humidity"):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY
            self._attr_min_humidity = item["range"]["min"]
            self._attr_max_humidity = item["range"]["max"]

        if item := capabilities.get("fan_speed"):
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = [i["value"] for i in item["modes"]]

    def internal_update(self, capabilities: dict, properties: dict):
        if "on" in capabilities:
            self.on_value = capabilities["on"]
        if self.hvac_instance in capabilities:
            self.hvac_value = capabilities[self.hvac_instance]

        # if instance on is False => state = OFF
        # else state = mode from instance thermostat
        # else state = ON
        if self.on_value is False:
            self._attr_hvac_mode = HVACMode.OFF
        elif self.hvac_value:
            self._attr_hvac_mode = HVACMode(self.hvac_value)
        else:
            self._attr_hvac_mode = self._attr_hvac_modes[0]

        if "fan_speed" in capabilities:
            self._attr_fan_mode = capabilities["fan_speed"]
        if self.preset_instance in capabilities:
            self._attr_preset_mode = capabilities[self.preset_instance]
        if "humidity" in capabilities:
            self._attr_target_humidity = capabilities["humidity"]
        if "temperature" in capabilities:
            self._attr_target_temperature = capabilities["temperature"]

        if "temperature" in properties:
            self._attr_current_temperature = properties["temperature"]
        if "humidity" in properties:
            self._attr_current_humidity = properties["humidity"]

    async def async_added_to_hass(self):
        if item := self.config.get("current_temperature"):
            on_remove = utils.track_template(self.hass, item, self.on_track_template)
            self.async_on_remove(on_remove)

    def on_track_template(self, value):
        try:
            self._attr_current_temperature = float(value)
        except:
            self._attr_current_temperature = None
        self._async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        if hvac_mode == HVACMode.OFF:
            kwargs = {"on": False}
        elif self.hvac_instance is None:
            kwargs = {"on": True}
        else:
            kwargs = (
                {"on": True, self.hvac_instance: str(hvac_mode)}
                if self._attr_hvac_mode == HVACMode.OFF
                else {self.hvac_instance: str(hvac_mode)}
            )

        await self.quasar.device_actions(self.device["id"], **kwargs)

    async def async_set_temperature(self, temperature: float, **kwargs):
        await self.quasar.device_action(self.device["id"], "temperature", temperature)

    async def async_set_fan_mode(self, fan_mode: str):
        await self.quasar.device_action(self.device["id"], "fan_speed", fan_mode)

    async def async_set_preset_mode(self, preset_mode: str):
        await self.quasar.device_action(
            self.device["id"], self.preset_instance, preset_mode
        )
