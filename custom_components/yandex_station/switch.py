import logging

from homeassistant.components.switch import SwitchEntity

from . import DOMAIN, YandexQuasar

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    if discovery_info is None:
        return

    quasar = hass.data[DOMAIN]['quasar']
    add_entities([YandexSwitch(quasar, discovery_info)], True)


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
