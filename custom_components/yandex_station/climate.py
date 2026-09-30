import asyncio
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION, UnitOfTemperature

from .core import utils
from .core.entity import YandexEntity
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

# https://developers.home-assistant.io/blog/2024/01/24/climate-climateentityfeatures-expanded
ONOFF = (
    (ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF)
    if (MAJOR_VERSION, MINOR_VERSION) >= (2024, 2)
    else 0
)

INCLUDE_TYPES = (
    "devices.types.purifier",
    "devices.types.thermostat",
    "devices.types.thermostat.ac",
    "devices.types.thermostat.heater",
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        YandexClimate(quasar, device, config)
        for quasar, device, config in hass_utils.incluce_devices(hass, entry)
        if device["type"] in INCLUDE_TYPES
    )
    # this should be fixed someday
    async_add_entities(
        YandexRemoteCarSeat(quasar, device, config)
        for quasar, device, config in hass_utils.incluce_devices(hass, entry)
        if device["type"] == "devices.types.remote_car.seat"
    )


# HA: auto, cool, dry, fan_only, heat; heat_cool, off
# Ya: auto, cool, dry, fan_only, heat; eco, turbo, quiet
HVAC_MODES = {
    "auto": HVACMode.AUTO,
    "cool": HVACMode.COOL,
    "dry": HVACMode.DRY,
    "fan_only": HVACMode.FAN_ONLY,
    "heat": HVACMode.HEAT,
}


def check_hvac_modes(item: dict) -> bool:
    return sum(1 for i in item["modes"] if i["value"] in HVAC_MODES) >= 2


class YandexClimate(ClimateEntity, YandexEntity):
    _attr_supported_features = ONOFF
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    hvac_instance: str = None  # thermostat or program
    preset_instance: str = None
    on_value: bool = None
    hvac_value: str = None
    # fix https://github.com/AlexxIT/YandexStation/issues/615
    assumed_hvac_mode: HVACMode = None

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
            self._attr_hvac_modes = [
                v for i in item["modes"] if (v := HVAC_MODES.get(i["value"]))
            ]
        elif self.device["type"] == "devices.types.purifier":
            self._attr_hvac_modes = [HVACMode.FAN_ONLY]
        elif "heat" in capabilities:
            self._attr_hvac_modes = [HVACMode.HEAT]
        else:
            self._attr_hvac_modes = [HVACMode.AUTO]

        if len(self._attr_hvac_modes) == 1:
            self.assumed_hvac_mode = self._attr_hvac_modes[0]

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
        # else state = assumed hvac_mode
        if self.on_value is False:
            self._attr_hvac_mode = HVACMode.OFF
        elif self.hvac_value:
            self._attr_hvac_mode = HVAC_MODES.get(self.hvac_value)
        else:
            self._attr_hvac_mode = self.assumed_hvac_mode

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
            on_remove = utils.track_template(self.hass, item, self.on_track_temperature)
            self.async_on_remove(on_remove)
        if item := self.config.get("current_humidity"):
            on_remove = utils.track_template(self.hass, item, self.on_track_humidity)
            self.async_on_remove(on_remove)

    def on_track_temperature(self, value):
        try:
            self._attr_current_temperature = float(value)
        except:
            self._attr_current_temperature = None
        self._async_write_ha_state()

    def on_track_humidity(self, value):
        try:
            self._attr_current_humidity = int(value)
        except:
            self._attr_current_humidity = None
        self._async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        if hvac_mode == HVACMode.OFF:
            await self.device_action("on", False)
        elif self.hvac_instance is None:
            await self.device_action("on", True)
        elif await self.internal_set_hvac_mode(str(hvac_mode)):
            self.assumed_hvac_mode = hvac_mode

    async def async_set_temperature(self, temperature: float, **kwargs):
        await self.device_action("temperature", temperature)

    async def async_set_fan_mode(self, fan_mode: str):
        await self.device_action("fan_speed", fan_mode)

    async def async_set_preset_mode(self, preset_mode: str):
        await self.device_action(self.preset_instance, preset_mode)

    async def internal_set_hvac_mode(self, value: str) -> bool:
        # https://github.com/AlexxIT/YandexStation/issues/577
        if self._attr_hvac_mode == HVACMode.OFF:
            await self.device_action("on", True)
            await asyncio.sleep(1)

        for _ in range(3):
            try:
                await self.device_action(self.hvac_instance, value)
                return True
            except Exception as e:
                # https://github.com/AlexxIT/YandexStation/issues/561
                if "DEVICE_OFF" in str(e):
                    await self.device_action("on", True)
                    await asyncio.sleep(1)
                else:
                    raise e

        return False


class YandexRemoteCarSeat(ClimateEntity, YandexEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ONOFF | ClimateEntityFeature.PRESET_MODE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]

    def internal_init(self, capabilities: dict, properties: dict):
        # {'instance': 'heating_mode', 'looped': False, 'name': 'режим обогрева', 'random_access': True, 'range': {'max': 3, 'min': 1, 'precision': 1}, 'retrievable': True, 'unit': ''}
        if mode := capabilities.get("heating_mode"):
            modes = range(mode["range"]["min"], mode["range"]["max"] + 1)
            self._attr_preset_modes = [str(i) for i in modes]

    def internal_update(self, capabilities: dict, properties: dict):
        if (value := capabilities.get("on")) is not None:
            self._attr_hvac_mode = HVACMode.HEAT if value else HVACMode.OFF

        if value := capabilities.get("heating_mode"):
            self._attr_preset_mode = str(value)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        if hvac_mode == HVACMode.OFF:
            await self.device_action("on", False)
        elif hvac_mode == HVACMode.HEAT:
            await self.device_action("on", True)

    async def async_set_preset_mode(self, preset_mode: str):
        await self.device_action("heating_mode", int(preset_mode))
