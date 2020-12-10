import logging

from homeassistant.components.switch import SwitchEntity

from . import DOMAIN, DATA_CONFIG, CONF_INCLUDE, YandexQuasar

_LOGGER = logging.getLogger(__name__)

DEVICES = ['devices.types.switch', 'devices.types.socket']


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]
    devices = [
        YandexSwitch(quasar, device)
        for device in quasar.devices
        if device['name'] in include and device['type'] in DEVICES
    ]
    async_add_entities(devices, True)


# noinspection PyAbstractClass
class YandexSwitch(SwitchEntity):
    _attrs = None
    _is_on = None

    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device

    @property
    def unique_id(self):
        return self.device['id'].replace('-', '')

    @property
    def name(self):
        return self.device['name']

    @property
    def should_poll(self):
        return True

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def device_state_attributes(self):
        return self._attrs

    async def async_update(self):
        data = await self.quasar.get_device(self.device['id'])
        for capability in data['capabilities']:
            if not capability['retrievable']:
                continue

            instance = capability['state']['instance']
            if instance == 'on':
                self._is_on = capability['state']['value']

        try:
            self._attrs = {
                p['parameters']['instance']: p['state']['value']
                for p in data['properties']
                if p['state']
            }
        except:
            _LOGGER.warning(f"Can't read properties: {data}")

    async def async_turn_on(self, **kwargs):
        await self.quasar.device_action(self.device['id'], on=True)

    async def async_turn_off(self, **kwargs):
        await self.quasar.device_action(self.device['id'], on=False)
