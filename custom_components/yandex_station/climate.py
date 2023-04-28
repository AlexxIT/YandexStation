import logging

from homeassistant.components.climate import (
    ClimateEntity,
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant

from . import DOMAIN, CONF_INCLUDE, DATA_CONFIG, TEMP_SENSOR, YandexQuasar

_LOGGER = logging.getLogger(__name__)

DEVICES = ["devices.types.thermostat.ac", "devices.types.thermostat"]


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]

    devices = []
    for device in quasar.devices:
        if (
            next((inc for inc in include if isinstance(inc, str) == False and inc["name"] == device["name"]), None)
            is not None
            and device["type"] in DEVICES
        ) or (device["name"] in include and device["type"] in DEVICES):
            include_data = next(
                (inc for inc in include if inc["name"] == device["name"]),
                {TEMP_SENSOR: None},
            )
            devices.append(
                YandexClimate(
                    quasar,
                    {**device, TEMP_SENSOR: include_data.get(TEMP_SENSOR, None)},
                    hass,
                )
            )
    async_add_entities(devices, True)


# noinspection PyAbstractClass
class YandexClimate(ClimateEntity):
    _min_temp = None
    _max_temp = None
    _precision = None
    _hvac_mode = None
    _hvac_modes = None
    _preset_mode = None
    _preset_modes = None
    _is_on = None
    _t_temp = None
    _c_temp = None
    _fan_mode = None
    _fan_modes = None
    _supported = 0

    def __init__(self, quasar: YandexQuasar, device: dict, hass: HomeAssistant):
        self.quasar = quasar
        self.device = device
        self.hass = hass

    @property
    def unique_id(self):
        return self.device["id"].replace("-", "")

    @property
    def name(self):
        return self.device["name"]

    @property
    def should_poll(self):
        return True

    @property
    def precision(self):
        return self._precision

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_mode(self):
        return self._hvac_mode if self._is_on else HVACMode.OFF

    @property
    def hvac_modes(self):
        return self._hvac_modes

    @property
    def preset_mode(self):
        return self._preset_mode

    @property
    def preset_modes(self):
        return self._preset_modes

    @property
    def current_temperature(self):
        if self._c_temp is None:
            if self.device[TEMP_SENSOR] is None:
                return self._t_temp
            if (self.hass.states.get(self.device[TEMP_SENSOR]) is None) | (self.hass.states.get(self.device[TEMP_SENSOR]).state == "unknown"):
                return self._t_temp
            return self.hass.states.get(self.device[TEMP_SENSOR]).state
        return self._c_temp

    @property
    def target_temperature(self):
        return self._t_temp

    @property
    def fan_mode(self):
        return self._fan_mode

    @property
    def fan_modes(self):
        return self._fan_modes

    @property
    def supported_features(self):
        return self._supported

    @property
    def min_temp(self):
        return self._min_temp

    @property
    def max_temp(self):
        return self._max_temp

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self.quasar.device_action(self.device["id"], on=False)
        elif hvac_mode == HVACMode.HEAT:
            if self._preset_modes is not None:
                await self.quasar.device_action(self.device["id"], on=True)
            else:
                await self.quasar.device_action(
                    self.device["id"], on=True, thermostat=hvac_mode
                )
        else:
            await self.quasar.device_action(
                self.device["id"], on=True, thermostat=hvac_mode
            )

    async def async_set_temperature(self, **kwargs):
        await self.quasar.device_action(
            self.device["id"], temperature=kwargs[ATTR_TEMPERATURE]
        )

    async def async_set_fan_mode(self, fan_mode):
        await self.quasar.device_action(self.device["id"], fan_speed=fan_mode)

    async def async_set_preset_mode(self, preset_mode):
        await self.quasar.device_action(self.device["id"], heat=preset_mode)

    async def init_params(self, capabilities: dict):
        for capability in capabilities:
            parameters = capability["parameters"]
            instance = parameters.get("instance")
            if instance == "temperature":
                self._supported |= ClimateEntityFeature.TARGET_TEMPERATURE
                range_ = parameters["range"]
                self._min_temp = range_["min"]
                self._max_temp = range_["max"]
                self._precision = range_["precision"]

            elif instance == "fan_speed":
                self._supported |= ClimateEntityFeature.FAN_MODE
                self._fan_modes = [p["value"] for p in parameters["modes"]]

            elif instance == "thermostat":
                self._hvac_modes = [HVACMode.OFF] + [
                    p["value"] for p in parameters["modes"]
                ]

            elif instance == "heat":
                self._supported |= ClimateEntityFeature.PRESET_MODE
                self._preset_modes = [p["value"] for p in parameters["modes"]]
                self._hvac_mode = HVACMode.HEAT
                self._hvac_modes = [HVACMode.HEAT, HVACMode.OFF]

    async def async_update(self):
        data = await self.quasar.get_device(self.device["id"])

        # first time init
        if self._is_on is None:
            await self.init_params(data["capabilities"])

        for capability in data["capabilities"]:
            if not capability["retrievable"]:
                continue

            instance = capability["state"]["instance"]
            if instance == "on":
                self._is_on = capability["state"]["value"]
            elif instance == "temperature":
                self._t_temp = capability["state"]["value"]
            elif instance == "fan_speed":
                self._fan_mode = capability["state"]["value"]
            elif instance == "thermostat":
                self._hvac_mode = capability["state"]["value"]
            elif instance == "heat":
                self._preset_mode = capability["state"]["value"]

        for property in data["properties"]:
            if not property["retrievable"]:
                continue

            instance = property["parameters"]["instance"]
            if instance == "temperature":
                self._c_temp = property["state"]["value"]
