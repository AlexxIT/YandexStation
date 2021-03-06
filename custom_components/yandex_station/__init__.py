import json
import logging
from typing import Mapping, List, Any

import voluptuous as vol
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_ID, \
    ATTR_MEDIA_CONTENT_TYPE, DOMAIN as DOMAIN_MP, SERVICE_PLAY_MEDIA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, ATTR_ENTITY_ID, \
    EVENT_HOMEASSISTANT_STOP, CONF_TOKEN, CONF_INCLUDE, CONF_DEVICES, \
    CONF_HOST, CONF_PORT, CONF_TIMEOUT, CONF_DEVICE
from homeassistant.core import ServiceCall, HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .browse_media import YandexMusicBrowser, MAP_MEDIA_TYPE_TO_BROWSE
from .const import CONF_WIDTH, CONF_HEIGHT, CONF_CACHE_TTL, CONF_LANGUAGE, \
    SUPPORTED_BROWSER_LANGUAGES, CONF_ROOT_OPTIONS, CONF_THUMBNAIL_RESOLUTION, \
    DOMAIN, CONF_TTS_NAME, CONF_INTENTS, CONF_RECOGNITION_LANG, CONF_PROXY, \
    CONF_DEBUG, CONF_MEDIA_BROWSER, DATA_CONFIG, DATA_SPEAKERS, DATA_MUSIC_BROWSER, \
    ROOT_MEDIA_CONTENT_TYPE, CONF_SHOW_HIDDEN, CONF_LYRICS, DATA_UPDATE_LISTENERS, ATTR_MESSAGE, ATTR_DEVICE, \
    ATTR_USERNAME, ATTR_UNIQUE_ID, ATTR_PASSWORD, ATTR_TEXT, ATTR_TOKEN
from .core import utils
from .core.yandex_glagol import YandexIOListener
from .core.yandex_quasar import YandexQuasar
from .core.yandex_session import YandexSession

_LOGGER = logging.getLogger(__name__)


def process_width_height_dict(resolution: dict):
    if CONF_WIDTH in resolution:
        if CONF_HEIGHT not in resolution:
            resolution[CONF_HEIGHT] = resolution[CONF_WIDTH]
    elif CONF_HEIGHT in resolution:
        resolution[CONF_WIDTH] = resolution[CONF_HEIGHT]
    else:
        raise vol.Invalid(f'at least one parameter ({CONF_WIDTH}, {CONF_HEIGHT}) must be provided')
    return f'{resolution[CONF_WIDTH]}x{resolution[CONF_HEIGHT]}'


def process_width_height_str(resolution: str):
    parts = resolution.split('x')

    try:
        width = int(parts[0])
        if len(parts) == 1:
            height = width
        elif len(parts) == 2:
            height = int(parts[1])
        else:
            raise vol.Invalid('one or two dimensional parameters are required')

        if width < 50 or height < 50:
            raise vol.Invalid('min dimension is 50px')
        if width > 1000 or height > 1000:
            raise vol.Invalid('max dimension is 1000px')

    except ValueError:
        raise vol.Invalid(f'dimensions must be presented in a <{CONF_WIDTH}>x<{CONF_HEIGHT}> format')

    return {CONF_WIDTH: width, CONF_HEIGHT: height}


MEDIA_BROWSER_CONFIG_SCHEMA = vol.Schema({
    vol.Optional(CONF_CACHE_TTL): cv.positive_float,
    vol.Optional(CONF_TIMEOUT): cv.positive_float,
    vol.Optional(CONF_LANGUAGE): vol.In(SUPPORTED_BROWSER_LANGUAGES),
    vol.Optional(CONF_SHOW_HIDDEN): cv.boolean,
    vol.Optional(CONF_LYRICS): cv.boolean,
    vol.Optional(CONF_ROOT_OPTIONS): vol.All(
        cv.ensure_list,
        [vol.All(
            vol.NotIn(ROOT_MEDIA_CONTENT_TYPE),
            vol.Any(
                vol.In(MAP_MEDIA_TYPE_TO_BROWSE.keys()),
                cv.string,
                #vol.Match(RE_MENU_OPTION_MEDIA)
            )
        )],
        vol.Length(min=1)
    ),
    vol.Optional(CONF_THUMBNAIL_RESOLUTION): vol.All(
        vol.Any(
            vol.All(cv.string, process_width_height_str),
            process_width_height_dict
        ),
        vol.Schema({
            vol.Optional(CONF_WIDTH): cv.positive_int,
            vol.Optional(CONF_HEIGHT): cv.positive_int,
        }),
    )
})

# USERNAME_VALIDATOR = vol.All(cv.string, lambda x: x if '@' in x else x + '@yandex.ru')
USERNAME_VALIDATOR = cv.string

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_USERNAME): USERNAME_VALIDATOR,
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
        vol.Optional(CONF_MEDIA_BROWSER): MEDIA_BROWSER_CONFIG_SCHEMA,
    }, extra=vol.ALLOW_EXTRA),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, hass_config: dict):
    """Main setup of component."""
    hass.data[DOMAIN] = {
        DATA_CONFIG: hass_config.get(DOMAIN) or {},
        DATA_SPEAKERS: {},
        DATA_MUSIC_BROWSER: {},
        DATA_UPDATE_LISTENERS: {}
    }

    await _init_local_discovery(hass)
    await _init_services(hass)
    await _setup_entry_from_config(hass)

    return True


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry):
    updated_browser_config = {**entry.data.get(CONF_MEDIA_BROWSER, {}),
                              **(entry.options or {}).get(CONF_MEDIA_BROWSER, {})}

    _LOGGER.debug('Updating config entry: browser_config=%s', updated_browser_config)
    music_browser: YandexMusicBrowser = hass.data[DOMAIN][DATA_MUSIC_BROWSER][entry.unique_id]
    music_browser.browser_config = updated_browser_config

    yandex: YandexSession = hass.data[DOMAIN][entry.unique_id].session

    # noinspection PyProtectedMember
    music_browser._original_client.token = await yandex.get_music_token(yandex.x_token)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    async def update_cookie_and_token(**kwargs):
        hass.config_entries.async_update_entry(entry, data=kwargs)

    session = async_create_clientsession(hass)
    yandex = YandexSession(session, **entry.data)
    yandex.music_token = await yandex.get_music_token(yandex.x_token)
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

    browser_config = {
        **config.get(CONF_MEDIA_BROWSER, {}),
        **entry.options.get(CONF_MEDIA_BROWSER, {})
    }

    music_client = await hass.async_add_executor_job(
        YandexMusicBrowser,
        yandex.music_token,
        browser_config,
    )
    # @TODO: add music token update listener

    hass.data[DOMAIN][DATA_MUSIC_BROWSER][entry.unique_id] = music_client

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

    hass.data[DOMAIN][DATA_UPDATE_LISTENERS][entry.unique_id] = entry.add_update_listener(
        async_update_entry
    )

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

_BASE_DEVICE_PARSE_SCHEMA = vol.Schema({
    vol.Exclusive(ATTR_ENTITY_ID, group_of_exclusion='selection'): cv.entity_ids,
    vol.Exclusive(ATTR_DEVICE, group_of_exclusion='selection'): vol.All(cv.ensure_list, [cv.string], vol.Length(min=1)),
})

SERVICE_SEND_COMMAND_ID = 'send_command'
SERVICE_SEND_COMMAND_SCHEMA = _BASE_DEVICE_PARSE_SCHEMA.extend({
    vol.Optional(ATTR_TEXT): cv.string,
}, extra=vol.ALLOW_EXTRA)

SERVICE_YANDEX_STATION_SAY_ID = 'yandex_station_say'
SERVICE_YANDEX_STATION_SAY_SCHEMA = _BASE_DEVICE_PARSE_SCHEMA.extend({
    vol.Required(ATTR_MESSAGE): cv.string,
}, extra=vol.ALLOW_EXTRA)

_UNIQUE_IDS_SCHEMA = vol.Schema({
    vol.Optional(ATTR_UNIQUE_ID): vol.All(cv.ensure_list, [cv.string], vol.Length(min=1)),
})

SERVICE_CHANGE_BROWSER_ACCOUNT_ID = 'change_browser_account'
SERVICE_CHANGE_BROWSER_ACCOUNT_SCHEMA = vol.Any(
    # Auth via username / password
    _UNIQUE_IDS_SCHEMA.extend({
        vol.Required(ATTR_USERNAME): USERNAME_VALIDATOR,
        vol.Required(ATTR_PASSWORD): cv.string,
    }),
    # Auth via token
    _UNIQUE_IDS_SCHEMA.extend({
        vol.Required(ATTR_TOKEN): cv.string,
    }),
    # Reset
    _UNIQUE_IDS_SCHEMA
)


async def _init_services(hass: HomeAssistant):
    """Init Yandex Station TTS service."""
    speakers: dict = hass.data[DOMAIN][DATA_SPEAKERS]

    def _parse_devices(data: Mapping[str, Any]) -> List[str]:
        if data.get(ATTR_ENTITY_ID):
            return [data[ATTR_ENTITY_ID]]
        if data.get(CONF_DEVICE):
            return utils.find_stations(speakers.values(), data[CONF_DEVICE])
        return utils.find_stations(speakers.values())

    async def send_command(call: ServiceCall):
        entity_ids = _parse_devices(call.data)

        _LOGGER.debug(f"Send command to: {entity_ids}")

        if not entity_ids:
            _LOGGER.error("Could not find entities to play")
            return

        data = {
            ATTR_ENTITY_ID: entity_ids,
            ATTR_MEDIA_CONTENT_ID: call.data.get(ATTR_TEXT),
            ATTR_MEDIA_CONTENT_TYPE: 'dialog',
        } if call.data.get('command') == 'dialog' else {
            ATTR_ENTITY_ID: entity_ids,
            ATTR_MEDIA_CONTENT_ID: json.dumps(dict(call.data)),
            ATTR_MEDIA_CONTENT_TYPE: 'json',
        }

        await hass.services.async_call(DOMAIN_MP, SERVICE_PLAY_MEDIA, data,
                                       blocking=True)

    hass.services.async_register(DOMAIN, SERVICE_SEND_COMMAND_ID, send_command)

    async def yandex_station_say(call: ServiceCall):
        entity_ids = _parse_devices(call.data)

        _LOGGER.debug(f"Yandex say to: {entity_ids}")

        if not entity_ids:
            _LOGGER.error("Entity_id parameter required")
            return

        data = {
            ATTR_MEDIA_CONTENT_ID: call.data.get(ATTR_MESSAGE),
            ATTR_MEDIA_CONTENT_TYPE: 'tts',
            ATTR_ENTITY_ID: entity_ids,
        }

        await hass.services.async_call(DOMAIN_MP, SERVICE_PLAY_MEDIA, data,
                                       blocking=True)

    config = hass.data[DOMAIN][DATA_CONFIG]
    service_name = config.get(CONF_TTS_NAME, SERVICE_YANDEX_STATION_SAY_ID)
    hass.services.async_register('tts', service_name, yandex_station_say,
                                 SERVICE_YANDEX_STATION_SAY_SCHEMA)

    external_browser_accounts = {}

    async def change_browser_account(call: ServiceCall):
        data = dict(call.data)
        music_browsers = hass.data[DOMAIN][DATA_MUSIC_BROWSER]

        unique_ids = data.get(ATTR_UNIQUE_ID, None)
        if unique_ids is None:
            unique_ids = music_browsers.keys()
        else:
            unique_ids = set(unique_ids)
            if unique_ids - music_browsers.keys():
                _LOGGER.error("unique_id(s) are not present in integrations registry")
                return

        if CONF_USERNAME in data and CONF_PASSWORD in data:
            username = data[CONF_USERNAME]

            notification_id = 'yandex_change_browser_auth:' + username
            if username in external_browser_accounts:
                session = external_browser_accounts[username]
                _LOGGER.debug('authenticating tested account %s', username)

            else:
                session = YandexSession(async_create_clientsession(hass))
                external_browser_accounts[username] = session
                _LOGGER.debug('authenticating new account %s', username)

            login_resp = await session.login_username(
                username=username,
                password=data[CONF_PASSWORD],
            )

            if login_resp.ok:
                if login_resp.x_token:
                    token = await session.get_music_token(login_resp.x_token)
                    hass.async_create_task(
                        hass.services.async_call(
                            'persistent_notification', 'dismiss',
                            service_data={
                                'notification_id': notification_id,
                            }
                        )
                    )
                else:
                    _LOGGER.error('x_token missing from response')
                    return

            elif login_resp.external_url:
                hass.async_create_task(
                    hass.services.async_call(
                        'persistent_notification', 'create',
                        service_data={
                            'notification_id': notification_id,
                            'title': 'Авторизация на яндекс',
                            'message': f'Аккаунт **{data[CONF_USERNAME]}** требует дополнительной авторизации. '
                                       f'[Перейдите по ссылке]({login_resp.external_url}), чтобы продолжить.',
                        }
                    )
                )
                _LOGGER.error('external authentication required (check notifications)')
                return

            else:
                _LOGGER.error('unsuccessful authentication: %s', login_resp.error)
                return
        elif CONF_TOKEN in data:
            token = data[CONF_TOKEN]
        else:
            _LOGGER.debug('Resetting original accounts for: "%s"', '", "'.join(unique_ids))
            for unique_id in music_browsers.keys() & unique_ids:
                music_browsers[unique_id].client = None
            return

        from yandex_music import Client
        from yandex_music.exceptions import YandexMusicError

        try:
            music_client = await hass.async_add_executor_job(Client.from_token, token)
            _LOGGER.debug('Replacement music client interface authentication successful')
        except ValueError as e:
            _LOGGER.error('data error: %s', e)
            return
        except YandexMusicError as e:
            _LOGGER.error('authentication error: %s', e)
            return

        _LOGGER.debug('Changing account for "%s"', '", "'.join(unique_ids))
        for unique_id in music_browsers.keys() & unique_ids:
            music_browsers[unique_id].client = music_client

    hass.services.async_register(DOMAIN, SERVICE_CHANGE_BROWSER_ACCOUNT_ID, change_browser_account,
                                 SERVICE_CHANGE_BROWSER_ACCOUNT_SCHEMA)


async def _setup_entry_from_config(hass: HomeAssistant):
    """Support legacy config from YAML."""
    config = hass.data[DOMAIN][DATA_CONFIG]
    if CONF_USERNAME not in config:
        return

    # check if already configured
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if config_entry.unique_id == config[CONF_USERNAME]:
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

    for domain in ('climate', 'light', 'remote', 'switch'):
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            entry, domain
        ))
