import json
import logging

import voluptuous as vol
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_ID, \
    ATTR_MEDIA_CONTENT_TYPE, DOMAIN as DOMAIN_MP, SERVICE_PLAY_MEDIA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, ATTR_ENTITY_ID, \
    EVENT_HOMEASSISTANT_STOP, CONF_TOKEN, CONF_INCLUDE, CONF_DEVICES, \
    CONF_HOST, CONF_PORT
from homeassistant.core import ServiceCall, HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .core import utils
from .core.yandex_glagol import YandexIOListener
from .core.yandex_quasar import YandexQuasar
from .core.yandex_session import YandexSession

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'yandex_station'

CONF_TTS_NAME = 'tts_service_name'
CONF_INTENTS = 'intents'
CONF_DEBUG = 'debug'
CONF_RECOGNITION_LANG = 'recognition_lang'
CONF_PROXY = 'proxy'

DATA_CONFIG = 'config'
DATA_SPEAKERS = 'speakers'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TOKEN): cv.string,
        vol.Optional(CONF_TTS_NAME): cv.string,
        vol.Optional(CONF_INTENTS): dict,
        vol.Optional(CONF_INCLUDE): cv.ensure_list,
        vol.Optional(CONF_DEVICES): {
            cv.string: vol.Schema({
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=1961): cv.port,
            }, extra=vol.ALLOW_EXTRA),
        },
        vol.Optional(CONF_RECOGNITION_LANG): cv.string,
        vol.Optional(CONF_PROXY): cv.string,
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
    }, extra=vol.ALLOW_EXTRA),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, hass_config: dict):
    """Main setup of component."""
    hass.data[DOMAIN] = {
        DATA_CONFIG: hass_config.get(DOMAIN) or {},
        DATA_SPEAKERS: {}
    }

    await _init_local_discovery(hass)
    await _init_services(hass)
    await _setup_entry_from_config(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    async def update_cookie_and_token(**kwargs):
        hass.config_entries.async_update_entry(entry, data=kwargs)

    session = async_create_clientsession(hass)
    yandex = YandexSession(session, **entry.data)
    yandex.add_update_listener(update_cookie_and_token)

    config = hass.data[DOMAIN][DATA_CONFIG]
    yandex.proxy = config.get(CONF_PROXY)

    if not await yandex.refresh_cookies():
        hass.components.persistent_notification.async_create(
            "Необходимо заново авторизоваться в Яндексе. Для этого [добавьте "
            "новую интеграцию](/config/integrations) с тем же логином.",
            title="Yandex.Station")
        return False

    quasar = YandexQuasar(yandex)
    await quasar.init()

    # entry.unique_id - user login
    hass.data[DOMAIN][entry.unique_id] = quasar

    # add stations to global list
    speakers = hass.data[DOMAIN][DATA_SPEAKERS]
    for speaker in quasar.speakers:
        did = speaker['quasar_info']['device_id']
        if did in speakers:
            speaker.update(speakers[did])
        speakers[did] = speaker

    await _setup_intents(hass, quasar)
    await _setup_include(hass, entry)
    await _setup_devices(hass, quasar)

    async def speaker_update(payload: dict):
        hass.bus.async_fire('yandex_speaker', payload)

    quasar.handle_updates(speaker_update)

    hass.async_create_task(hass.config_entries.async_forward_entry_setup(
        entry, 'media_player'
    ))
    return True


async def _init_local_discovery(hass: HomeAssistant):
    """Init descovery local speakers with Zeroconf (mDNS)."""
    speakers: dict = hass.data[DOMAIN][DATA_SPEAKERS]

    async def found_local_speaker(info: dict):
        speaker = speakers.setdefault(info['device_id'], {})
        speaker.update(info)
        if 'entity' in speaker:
            await speaker['entity'].init_local_mode()

    zeroconf = await utils.get_zeroconf_singleton(hass)

    listener = YandexIOListener(hass.loop)
    listener.start(found_local_speaker, zeroconf)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, listener.stop)


async def _init_services(hass: HomeAssistant):
    """Init Yandex Station TTS service."""
    speakers: dict = hass.data[DOMAIN][DATA_SPEAKERS]

    async def send_command(call: ServiceCall):
        data = dict(call.data)

        device = data.pop('device', None)
        entity_ids = (data.pop(ATTR_ENTITY_ID, None) or
                      utils.find_station(speakers.values(), device))

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

    async def yandex_station_say(call: ServiceCall):
        entity_ids = (call.data.get(ATTR_ENTITY_ID) or
                      utils.find_station(speakers.values()))

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

        if 'options' in call.data:
            data['extra'] = call.data['options']

        await hass.services.async_call(DOMAIN_MP, SERVICE_PLAY_MEDIA, data,
                                       blocking=True)

    config = hass.data[DOMAIN][DATA_CONFIG]
    service_name = config.get(CONF_TTS_NAME, 'yandex_station_say')
    hass.services.async_register('tts', service_name, yandex_station_say)


async def _setup_entry_from_config(hass: HomeAssistant):
    """Support legacy config from YAML."""
    config = hass.data[DOMAIN][DATA_CONFIG]
    if CONF_USERNAME not in config:
        return

    # check if already configured
    for entrie in hass.config_entries.async_entries(DOMAIN):
        if entrie.unique_id == config[CONF_USERNAME]:
            return

    # load config/.yandex_station.json
    x_token = utils.load_token_from_json(hass)
    if x_token:
        config['x_token'] = x_token

    # need username and token or password
    if 'x_token' not in config and CONF_PASSWORD not in config:
        return

    hass.async_create_task(hass.config_entries.flow.async_init(
        DOMAIN, context={'source': SOURCE_IMPORT}, data=config
    ))


async def _setup_intents(hass: HomeAssistant, quasar: YandexQuasar):
    """Setup Intents MediaPlayer and scenarios for Yandex Account."""
    config = hass.data[DOMAIN][DATA_CONFIG]
    if CONF_INTENTS not in config:
        return

    intents: dict = config[CONF_INTENTS]

    if CONF_INTENTS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][CONF_INTENTS] = True
        discovered = {CONF_INTENTS: list(intents.keys())}
        hass.async_create_task(discovery.async_load_platform(
            hass, DOMAIN_MP, DOMAIN, discovered, config))

    if quasar.hass_id:
        for i, intent in enumerate(intents.keys(), 1):
            try:
                await quasar.add_intent(intent, intents[intent], i)
            except:
                pass


async def _setup_devices(hass: HomeAssistant, quasar: YandexQuasar):
    """Set speakers additional config from YAML."""
    config = hass.data[DOMAIN][DATA_CONFIG]
    if CONF_DEVICES not in config:
        return

    confdevices = config[CONF_DEVICES]

    for device in quasar.speakers:
        did = device['quasar_info']['device_id']
        if did in confdevices:
            device.update(confdevices[did])


async def _setup_include(hass: HomeAssistant, entry: ConfigEntry):
    """Setup additional devices from Yandex account."""
    config = hass.data[DOMAIN][DATA_CONFIG]
    if CONF_INCLUDE not in config:
        return

    for domain in ('climate', 'light', 'remote', 'switch', 'vacuum'):
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            entry, domain
        ))
