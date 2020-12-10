from homeassistant.components.light import LightEntity, SUPPORT_BRIGHTNESS, \
    ATTR_BRIGHTNESS, SUPPORT_EFFECT, ATTR_EFFECT, ATTR_HS_COLOR

from . import DOMAIN, DATA_CONFIG, CONF_INCLUDE, YandexQuasar

DEVICES = ['devices.types.light']


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]
    devices = [
        YandexLight(quasar, device)
        for device in quasar.devices
        if device['name'] in include and device['type'] in DEVICES
    ]
    async_add_entities(devices, True)


# noinspection PyAbstractClass
class YandexLight(LightEntity):
    _brightness = None
    _is_on = None
    _hs_color = None
    _supported_features = 0
    _effects = None

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
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return self._hs_color

    @property
    def effect_list(self):
        return list(self._effects.keys())

    @property
    def supported_features(self):
        return self._supported_features

    @property
    def state_attributes(self):
        """HS color attribute without SUPPORT_COLOR. Yandex don't support color
        change."""
        if not self.is_on:
            return None

        data = {}
        if self.brightness:
            data[ATTR_BRIGHTNESS] = self.brightness
        if self.hs_color:
            data[ATTR_HS_COLOR] = self.hs_color
        return data

    async def async_added_to_hass(self):
        data = await self.quasar.get_device(self.device['id'])
        for capability in data['capabilities']:
            instance = capability['parameters'].get('instance')
            if instance == 'color':
                self._effects = {
                    p['name']: p['id']
                    for p in capability['parameters']['palette']
                }
                self._supported_features |= SUPPORT_EFFECT
            elif instance == 'brightness':
                self._supported_features |= SUPPORT_BRIGHTNESS

    async def async_update(self):
        data = await self.quasar.get_device(self.device['id'])
        for capability in data['capabilities']:
            if not capability['retrievable']:
                continue

            instance = capability['state']['instance']
            if instance == 'on':
                self._is_on = capability['state']['value']
            elif instance == 'color':
                raw = capability['state']['value']['value']
                self._hs_color = [raw['h'], raw['s']]
            elif instance == 'brightness':
                self._brightness = round(capability['state']['value'] * 2.55)

    async def async_turn_on(self, **kwargs):
        """Yandex don't support hsv, rgb and temp via this API"""
        payload = {}

        if ATTR_BRIGHTNESS in kwargs:
            payload['brightness'] = round(kwargs[ATTR_BRIGHTNESS] / 2.55)

        if ATTR_EFFECT in kwargs:
            ef = kwargs[ATTR_EFFECT]
            payload['color'] = self._effects[ef]

        if not payload:
            payload['on'] = True

        await self.quasar.device_action(self.device['id'], **payload)

    async def async_turn_off(self, **kwargs):
        await self.quasar.device_action(self.device['id'], on=False)
