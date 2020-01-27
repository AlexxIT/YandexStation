from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import ServiceCall

from . import utils

DOMAIN = 'yandex_station'


def setup(hass, hass_config):
    config = hass_config[DOMAIN]

    filename = hass.config.path(f".{DOMAIN}.txt")

    if CONF_TOKEN in config:
        yandex_token = config[CONF_TOKEN]
    else:
        yandex_token = utils.load_token(filename)

    if not yandex_token:
        yandex_token = utils.get_yandex_token(config[CONF_USERNAME],
                                              config[CONF_PASSWORD])
        utils.save_token(filename, yandex_token)

    assert yandex_token, "No token found"

    async def play_media(call: ServiceCall):
        data = dict(call.data)
        device = data.pop('device', None)
        host = data.pop('host')
        utils.send_to_station(yandex_token, device, host, data)

    hass.services.register(DOMAIN, 'send_command', play_media)

    return True
