import json
import logging

import voluptuous as vol
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_ID, \
    ATTR_MEDIA_CONTENT_TYPE, DOMAIN as DOMAIN_MP, SERVICE_PLAY_MEDIA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, ATTR_ENTITY_ID, \
    EVENT_HOMEASSISTANT_STOP, CONF_TOKEN, CONF_INCLUDE, CONF_DEVICES, \
    CONF_HOST, CONF_PORT
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import HomeAssistantType

from . import utils
from .yandex_glagol import YandexIOListener
from .yandex_quasar import YandexQuasar

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'yandex_station'

CONF_TTS_NAME = 'tts_service_name'
CONF_INTENTS = 'intents'
CONF_DEBUG = 'debug'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TOKEN): cv.string,
        vol.Optional(CONF_TTS_NAME, default='yandex_station_say'): cv.string,
        vol.Optional(CONF_INTENTS): dict,
        vol.Optional(CONF_INCLUDE): cv.ensure_list,
        vol.Optional(CONF_DEVICES): {
            cv.string: vol.Schema({
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=1961): cv.port,
            }, extra=vol.ALLOW_EXTRA),
        },
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
    }, extra=vol.ALLOW_EXTRA),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistantType, hass_config: dict):
    config: dict = hass_config[DOMAIN]

    # init debug if needed
    if config[CONF_DEBUG]:
        utils.YandexDebug(hass, _LOGGER)

    cachefile = hass.config.path(f".{DOMAIN}.json")

    # нужна собственная сессия со своими кукисами
    session = async_create_clientsession(hass)

    hass.data[DOMAIN] = quasar = YandexQuasar(session)

    # если есть логин/пароль - запускаем облачное подключение
    if CONF_USERNAME in config and CONF_PASSWORD in config:
        devices = await quasar.init(
            config[CONF_USERNAME], config[CONF_PASSWORD], cachefile)

    # если есть токен - то только локальное
    elif CONF_TOKEN in config:
        devices = await quasar.load_local_speakers(config[CONF_TOKEN])

    else:
        await utils.error(hass, "Нужны либо логин/пароль, либо token")
        return False

    if not devices:
        await utils.error(hass, "В аккаунте нет устройств")
        return False

    confdevices = config.get(CONF_DEVICES)
    if confdevices:
        for device in devices:
            did = device['device_id']
            if did in confdevices:
                device.update(confdevices[did])

    utils.clean_v1(hass.config)

    # create send_command service

    async def send_command(call: ServiceCall):
        data = dict(call.data)

        device = data.pop('device', None)
        entity_ids = (data.pop(ATTR_ENTITY_ID, None) or
                      utils.find_station(devices, device))

        _LOGGER.debug(f"Send command to: {entity_ids}")

        if not entity_ids:
            _LOGGER.error("Entity_id parameter required")
            return

        data = {
            ATTR_ENTITY_ID: entity_ids,
            ATTR_MEDIA_CONTENT_ID: data.get('text'),
            ATTR_MEDIA_CONTENT_TYPE: 'dialog',
        } if data.get('command') == 'dialog' else {
            ATTR_ENTITY_ID: entity_ids,
            ATTR_MEDIA_CONTENT_ID: json.dumps(data),
            ATTR_MEDIA_CONTENT_TYPE: 'json',
        }

        await hass.services.async_call(DOMAIN_MP, SERVICE_PLAY_MEDIA, data,
                                       blocking=True)

    hass.services.async_register(DOMAIN, 'send_command', send_command)

    # create TTS service

    async def yandex_station_say(call: ServiceCall):
        entity_ids = (call.data.get(ATTR_ENTITY_ID) or
                      utils.find_station(devices))

        _LOGGER.debug(f"Yandex say to: {entity_ids}")

        if not entity_ids:
            _LOGGER.error("Entity_id parameter required")
            return

        message = call.data.get('message')

        data = {
            ATTR_MEDIA_CONTENT_ID: message,
            ATTR_MEDIA_CONTENT_TYPE: 'tts',
            ATTR_ENTITY_ID: entity_ids,
        }

        await hass.services.async_call(DOMAIN_MP, SERVICE_PLAY_MEDIA, data,
                                       blocking=True)

    hass.services.async_register('tts', config[CONF_TTS_NAME],
                                 yandex_station_say)

    # создаём все колонки при облачном подключении
    if quasar.main_token:
        # настраиваем все колонки в облачном режиме
        for device in devices:
            info = {'device_id': device['device_id'], 'name': device['name'],
                    'platform': device['platform']}
            _LOGGER.debug(f"Инициализация: {info}")

            hass.async_create_task(discovery.async_load_platform(
                hass, DOMAIN_MP, DOMAIN, device, hass_config))

        # создаём служебный медиаплеер
        if CONF_INTENTS in config:
            intents: dict = config[CONF_INTENTS]

            hass.async_create_task(discovery.async_load_platform(
                hass, DOMAIN_MP, DOMAIN, list(intents.keys()), hass_config))

            if quasar.hass_id:
                for i, intent in enumerate(intents.keys(), 1):
                    try:
                        await quasar.add_intent(intent, intents[intent], i)
                    except:
                        pass

        # создаём устройства умного дома Яндекса (пока только кондеи)
        if CONF_INCLUDE in config:
            for device in quasar.devices:
                if device['name'] in config[CONF_INCLUDE]:
                    hass.async_create_task(discovery.async_load_platform(
                        hass, 'climate', DOMAIN, device, hass_config))

    async def found_local_device(info: dict):
        """Сообщение от Zeroconf (mDNS).

        :param info: {device_id, platform, host, port}
        """
        _LOGGER.debug(f"mDNS: {info}")

        await quasar.init_local(cachefile)

        for device in devices:
            if info['device_id'] != device['device_id']:
                continue

            device['host'] = info['host']
            device['port'] = info['port']

            if 'entity' not in device:
                hass.async_create_task(discovery.async_load_platform(
                    hass, DOMAIN_MP, DOMAIN, device, hass_config))

            elif device['entity']:
                await device['entity'].init_local_mode()

            break

    zeroconf = await utils.get_zeroconf_singleton(hass)

    listener = YandexIOListener(hass.loop)
    listener.start(found_local_device, zeroconf)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, listener.stop)

    return True
