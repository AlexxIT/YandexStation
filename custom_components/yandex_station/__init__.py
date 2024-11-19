import logging

import voluptuous as vol
from homeassistant.components.binary_sensor import HomeAssistant  # important for tests
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STOP,
    CONF_TOKEN,
    CONF_INCLUDE,
    CONF_DEVICES,
    CONF_HOST,
    CONF_PORT,
    CONF_DOMAIN,
    MAJOR_VERSION,
    MINOR_VERSION,
)
from homeassistant.core import ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client as ac,
    config_validation as cv,
    discovery,
    device_registry as dr,
)

from .core import utils
from .core.const import (
    CONF_INTENTS,
    CONF_MEDIA_PLAYERS,
    DATA_CONFIG,
    DATA_SPEAKERS,
    DOMAIN,
)
from .core.yandex_glagol import YandexIOListener
from .core.yandex_quasar import YandexQuasar
from .core.yandex_session import YandexSession
from .core.yandex_station import YandexStationBase
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    "button",
    "calendar",
    "camera",
    "climate",
    "cover",
    "humidifier",
    "light",
    "media_player",
    "number",
    "remote",
    "select",
    "switch",
    "vacuum",
    "sensor",
    "water_heater",
]
PLATFORMS2 = ["camera", "conversation", "media_player", "select"]  # only for speakers

CONF_TTS_NAME = "tts_service_name"
CONF_DEBUG = "debug"
CONF_RECOGNITION_LANG = "recognition_lang"
CONF_PROXY = "proxy"
CONF_SSL = "ssl"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TOKEN): cv.string,
                vol.Optional(CONF_TTS_NAME): cv.string,
                vol.Optional(CONF_INTENTS): dict,
                vol.Optional(CONF_INCLUDE): cv.ensure_list,
                vol.Optional(CONF_DEVICES): {
                    cv.string: vol.Schema(
                        {
                            vol.Optional(CONF_HOST): cv.string,
                            vol.Optional(CONF_PORT, default=1961): cv.port,
                        },
                        extra=vol.ALLOW_EXTRA,
                    ),
                },
                vol.Optional(CONF_MEDIA_PLAYERS): vol.Any(dict, list),
                vol.Optional(CONF_RECOGNITION_LANG): cv.string,
                vol.Optional(CONF_DOMAIN): cv.string,
                vol.Optional(CONF_PROXY): cv.string,
                vol.Optional(CONF_SSL): cv.boolean,
                vol.Optional(CONF_DEBUG, default=False): cv.boolean,
            },
            extra=vol.ALLOW_EXTRA,
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, hass_config: dict):
    config: dict = hass_config.get(DOMAIN) or {}
    hass.data[DOMAIN] = {DATA_CONFIG: config, DATA_SPEAKERS: {}}

    if CONF_RECOGNITION_LANG in config:
        utils.fix_recognition_lang(
            hass, "frontend_latest", config[CONF_RECOGNITION_LANG]
        )

    YandexSession.domain = config.get(CONF_DOMAIN)
    YandexSession.proxy = config.get(CONF_PROXY)
    YandexSession.ssl = config.get(CONF_SSL)

    await _init_local_discovery(hass)
    await _init_services(hass)
    await _setup_entry_from_config(hass)

    if (MAJOR_VERSION, MINOR_VERSION) >= (2024, 5):
        # can't use ImportError, because bug with "Detected blocking call"
        PLATFORMS.append("conversation")

    hass.http.register_view(utils.StreamingView(hass))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    async def update_cookie_and_token(**kwargs):
        hass.config_entries.async_update_entry(entry, data=kwargs)

    session = ac.async_create_clientsession(hass)
    yandex = YandexSession(session, **entry.data)
    yandex.add_update_listener(update_cookie_and_token)

    try:
        ok = await yandex.refresh_cookies()
    except Exception as e:
        raise ConfigEntryNotReady from e

    if not ok:
        hass.components.persistent_notification.async_create(
            "Необходимо заново авторизоваться в Яндексе. Для этого [добавьте "
            "новую интеграцию](/config/integrations) с тем же логином.",
            title="Yandex.Station",
        )
        return False

    quasar = YandexQuasar(yandex)
    await quasar.init()

    hass_utils.load_fake_devies(hass, quasar)

    # entry.unique_id - user login
    hass.data[DOMAIN][entry.unique_id] = quasar

    # add stations to global list
    speakers = hass.data[DOMAIN][DATA_SPEAKERS]
    for device in quasar.speakers + quasar.modules:
        did = device["quasar_info"]["device_id"]
        if did in speakers:
            device.update(speakers[did])
        speakers[did] = device

    await _setup_intents(hass, quasar)
    await _setup_devices(hass, quasar)

    if not entry.update_listeners:
        entry.add_update_listener(async_update_options)

    quasar.start()

    platforms = PLATFORMS if hass_utils.incluce_devices(hass, entry) else PLATFORMS2
    setattr(quasar, "platforms", platforms)
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry):
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]
    quasar.stop()

    platforms = getattr(quasar, "platforms")
    return await hass.config_entries.async_unload_platforms(entry, platforms)


async def _init_local_discovery(hass: HomeAssistant):
    """Init descovery local speakers with Zeroconf (mDNS)."""
    speakers: dict = hass.data[DOMAIN][DATA_SPEAKERS]

    async def found_local_speaker(info: dict):
        speaker = speakers.setdefault(info["device_id"], {})
        speaker.update(info)
        entity: YandexStationBase = speaker.get("entity")
        if entity and entity.hass:
            await entity.init_local_mode()
            entity.async_write_ha_state()

    zeroconf = await utils.get_zeroconf_singleton(hass)

    listener = YandexIOListener(
        lambda info: hass.create_task(found_local_speaker(info))
    )
    listener.start(zeroconf)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, listener.stop)


async def _init_services(hass: HomeAssistant):
    """Init Yandex Station TTS service."""
    speakers: dict = hass.data[DOMAIN][DATA_SPEAKERS]

    try:
        # starting from Home Assistant 2023.7
        from homeassistant.core import ServiceResponse, SupportsResponse
        from homeassistant.helpers import service

        async def send_command(call: ServiceCall) -> ServiceResponse:
            selected = service.async_extract_referenced_entity_ids(hass, call)
            entity_ids = selected.referenced | selected.indirectly_referenced
            for speaker in speakers.values():
                entity: YandexStationBase = speaker.get("entity")
                if not entity or entity.entity_id not in entity_ids or not entity.glagol:
                    continue
                data = service.remove_entity_service_fields(call)
                data.setdefault("command", "sendText")
                return await entity.glagol.send(data)
            return {"error": "Entity not found"}

        hass.services.async_register(
            DOMAIN,
            "send_command",
            send_command,
            supports_response=SupportsResponse.OPTIONAL,
        )
    except ImportError as e:
        _LOGGER.warning(repr(e))

    async def yandex_station_say(call: ServiceCall):
        entity_ids = call.data.get(ATTR_ENTITY_ID) or utils.find_station(
            speakers.values()
        )

        _LOGGER.debug(f"Yandex say to: {entity_ids}")

        if not entity_ids:
            _LOGGER.error("Entity_id parameter required")
            return

        message = call.data.get("message")

        data = {
            ATTR_MEDIA_CONTENT_ID: message,
            ATTR_MEDIA_CONTENT_TYPE: "tts",
            ATTR_ENTITY_ID: entity_ids,
        }

        if "options" in call.data:
            data["extra"] = call.data["options"]

        await hass.services.async_call(
            MEDIA_DOMAIN, SERVICE_PLAY_MEDIA, data, blocking=True
        )

    config = hass.data[DOMAIN][DATA_CONFIG]
    service_name = config.get(CONF_TTS_NAME, "yandex_station_say")
    hass.services.async_register("tts", service_name, yandex_station_say)


async def _setup_entry_from_config(hass: HomeAssistant):
    """Support legacy config from YAML."""
    config = hass.data[DOMAIN][DATA_CONFIG]
    if CONF_USERNAME not in config:
        return

    # check if already configured
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == config[CONF_USERNAME]:
            return

    if x_token := utils.load_token_from_json(hass):
        config["x_token"] = x_token

    # need username and token or password
    if "x_token" not in config and CONF_PASSWORD not in config:
        return

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def _setup_intents(hass: HomeAssistant, quasar: YandexQuasar):
    """Setup Intents MediaPlayer and scenarios for Yandex Account."""
    config = hass.data[DOMAIN][DATA_CONFIG]
    if CONF_INTENTS not in config:
        return

    intents: dict = config[CONF_INTENTS]

    if CONF_INTENTS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][CONF_INTENTS] = True
        discovered = {CONF_INTENTS: list(intents.keys())}
        hass.async_create_task(
            discovery.async_load_platform(
                hass, MEDIA_DOMAIN, DOMAIN, discovered, config
            )
        )

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

    for device in quasar.speakers + quasar.modules:
        did = device["quasar_info"]["device_id"]
        if upd := confdevices.get(did) or confdevices.get(did.lower()):
            device.update(upd)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Supported from Hass v2022.3"""
    dr.async_get(hass).async_remove_device(device.id)
    return True
