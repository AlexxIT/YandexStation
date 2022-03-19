import logging

from homeassistant.components.water_heater import WaterHeaterEntity, \
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE, SUPPORT_AWAY_MODE
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE

from . import DOMAIN, CONF_INCLUDE, DATA_CONFIG, YandexQuasar

_LOGGER = logging.getLogger(__name__)

DEVICES = ['devices.types.cooking.kettle']


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]
    devices = [
        YandexKettle(quasar, device)
        for device in quasar.devices
        if device['name'] in include and device['type'] in DEVICES
    ]
    async_add_entities(devices, True)


class YandexKettle(WaterHeaterEntity):
    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device

        self._attr_should_poll = True
        self._attr_supported_features = 0
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_name = device['name']
        self._attr_unique_id = device['id'].replace('-', '')

    async def init_params(self, capabilities: list):
        self._attr_operation_list = ["on", "off"]
        self._attr_supported_features |= SUPPORT_OPERATION_MODE

        for cap in capabilities:
            # there is no instance for 'on' capability, but this capability
            # doesn't have useful init params
            if 'instance' not in cap['parameters']:
                continue

            inst = cap['parameters']['instance']
            if inst == 'temperature':
                assert cap['parameters']['unit'] == 'unit.temperature.celsius'
                self._attr_min_temp = cap['parameters']['range']['min']
                self._attr_max_temp = cap['parameters']['range']['max']
                self._attr_precision = cap['parameters']['range']['precision']
                self._attr_supported_features |= SUPPORT_TARGET_TEMPERATURE
            elif inst == 'tea_mode':
                self._attr_operation_list += [
                    mode['value'] for mode in
                    cap['parameters']['modes']
                ]
            elif inst == 'mute':
                pass
            elif inst == 'keep_warm':
                self._attr_supported_features |= SUPPORT_AWAY_MODE

    async def async_update(self):
        data = await self.quasar.get_device(self.device['id'])

        try:
            if self._attr_current_operation is None:
                await self.init_params(data['capabilities'])

            self._attr_available = data['state'] == 'online'

            for cap in data['capabilities']:
                if not cap['retrievable']:
                    continue

                inst = cap['state']['instance']
                if inst == 'on':
                    self._attr_current_operation = \
                        'on' if cap['state']['value'] else 'off'
                elif inst == 'temperature':
                    self._attr_target_temperature = cap['state']['value']
                elif inst == 'tea_mode':
                    if self._attr_current_operation == 'on':
                        self._attr_current_operation = cap['state']['value']
                elif inst == 'mute':
                    pass
                elif inst == 'keep_warm':
                    self._attr_is_away_mode_on = cap['state']['value']

            for prop in data['properties']:
                if not prop['retrievable']:
                    continue

                if prop['parameters']['instance'] == 'temperature':
                    value = prop['state']['value'] if prop['state'] else None
                    self._attr_current_temperature = value

        except:
            _LOGGER.exception(data)

    async def async_set_operation_mode(self, operation_mode):
        if operation_mode == "on":
            kwargs = {"on": True}
        elif operation_mode == "off":
            kwargs = {"on": False}
        else:
            kwargs = {"tea_mode": operation_mode}

        await self.quasar.device_action(self.device['id'], **kwargs)

    async def async_set_temperature(self, **kwargs):
        value = round(kwargs[ATTR_TEMPERATURE] / self._attr_precision) * \
                self._attr_precision
        await self.quasar.device_action(self.device['id'], temperature=value)

    async def async_turn_away_mode_on(self):
        await self.quasar.device_action(self.device['id'], keep_warm=True)

    async def async_turn_away_mode_off(self):
        await self.quasar.device_action(self.device['id'], keep_warm=False)
