import logging

from homeassistant.components.climate import ClimateEntity, HVAC_MODE_OFF, \
    SUPPORT_FAN_MODE, SUPPORT_TARGET_TEMPERATURE
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE

from . import DOMAIN, YandexQuasar

_LOGGER = logging.getLogger(__name__)


# noinspection PyUnusedLocal
async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    if discovery_info is None:
        return

    quasar = hass.data[DOMAIN]['quasar']
    add_entities([YandexClimate(quasar, discovery_info)])


class YandexClimate(ClimateEntity):
    _min_temp = None
    _max_temp = None
    _precision = None
    _hvac_mode = None
    _hvac_modes = [HVAC_MODE_OFF]
    _is_on = None
    _temp = None
    _name = None
    _fan_mode = None
    _fan_modes = None
    _supported = 0

    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device

    async def async_added_to_hass(self):
        self._name = self.device['name']
        self.async_schedule_update_ha_state(True)

    @property
    def unique_id(self):
        return self.device['id'].replace('-', '')

    @property
    def name(self):
        return self._name

    @property
    def should_poll(self) -> bool:
        return True

    @property
    def precision(self):
        """Return the precision of the system."""
        return self._precision

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self._hvac_mode if self._is_on else HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._hvac_modes

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._temp

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_modes

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.quasar.device_action(self.device['id'], on=False)

        else:
            await self.quasar.device_action(self.device['id'], on=True,
                                            thermostat=hvac_mode)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self.quasar.device_action(self.device['id'],
                                        temperature=kwargs[ATTR_TEMPERATURE])

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        await self.quasar.device_action(self.device['id'], fan_speed=fan_mode)

    async def async_update(self):
        data = await self.quasar.get_device(self.device['id'])

        # first time init
        if self._is_on is None:
            for d in data['capabilities']:
                if d['state']['instance'] == 'temperature':
                    self._supported |= SUPPORT_TARGET_TEMPERATURE
                    range_ = d['parameters']['range']
                    self._min_temp = range_['min']
                    self._max_temp = range_['max']
                    self._precision = range_['precision']

                elif d['state']['instance'] == 'fan_speed':
                    self._supported |= SUPPORT_FAN_MODE
                    self._fan_modes = [
                        p['value'] for p in d['parameters']['modes']
                    ]

                elif d['state']['instance'] == 'thermostat':
                    self._hvac_modes += [
                        p['value'] for p in d['parameters']['modes']
                    ]

        for d in data['capabilities']:
            if d['state']['instance'] == 'on':
                self._is_on = d['state']['value']

            elif d['state']['instance'] == 'temperature':
                self._temp = d['state']['value']

            elif d['state']['instance'] == 'fan_speed':
                self._fan_mode = d['state']['value']

            elif d['state']['instance'] == 'thermostat':
                self._hvac_mode = d['state']['value']
