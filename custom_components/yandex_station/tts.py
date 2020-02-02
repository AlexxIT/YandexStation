import hashlib

from homeassistant.components.tts import Provider

from . import DOMAIN


async def async_get_engine(hass, config, discovery_info=None):
    if discovery_info is None:
        return
    return YandexTTSProvider()


class YandexTTSProvider(Provider):
    @property
    def default_language(self):
        return 'ru'

    @property
    def supported_languages(self):
        return ['ru']

    async def async_get_tts_audio(self, message, language, options=None):
        hash_ = hashlib.sha1(bytes(message, 'utf-8')).hexdigest()
        self.hass.data[DOMAIN][hash_] = message
        return 'tmp', b''
