import logging
from datetime import timedelta

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import CONF_INCLUDE

from .core import utils
from .core.const import CONF_INTENTS, DATA_CONFIG, DOMAIN
from .core.entity import YandexEntity
from .core.yandex_quasar import YandexQuasar
from .core.yandex_station import YandexStation, YandexModule

_LOGGER = logging.getLogger(__name__)

# update speaker online state once per 5 minutes
SCAN_INTERVAL = timedelta(minutes=5)

INCLUDE_TYPES = [
    "devices.types.media_device.receiver",
    "devices.types.media_device.tv",
    "devices.types.media_device.tv_box",
]


async def async_setup_entry(hass, entry, async_add_entities):
    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]

    # add Yandex stations
    entities = []
    for speaker in await quasar.load_speakers():
        speaker["entity"] = entity = YandexStation(quasar, speaker)
        entities.append(entity)
    for module in quasar.modules:
        module["entity"] = entity = YandexModule(quasar, module)
        entities.append(entity)
    async_add_entities(entities, True)

    # add Quasar TVs
    if CONF_INCLUDE not in hass.data[DOMAIN][DATA_CONFIG]:
        return

    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    entities = [
        YandexMediaPlayer(quasar, device, config)
        for device in quasar.devices
        if (config := utils.device_include(device, include, INCLUDE_TYPES))
    ]
    async_add_entities(entities, True)


# noinspection PyUnusedLocal
def setup_platform(hass, config, add_entities, discovery_info=None):
    # only intents setup via setup platform
    intents = discovery_info[CONF_INTENTS]
    add_entities([YandexIntents(intents)])


# noinspection PyAbstractClass
class YandexIntents(MediaPlayerEntity):
    _attr_name = "Yandex Intents"
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    def __init__(self, intents: list):
        self.intents = intents

    async def async_volume_up(self):
        pass

    async def async_volume_down(self):
        pass

    async def async_set_volume_level(self, volume):
        index = int(volume * 100) - 1
        if index < len(self.intents):
            text = self.intents[index]
            _LOGGER.debug(f"Получена команда: {text}")
            self.hass.bus.async_fire("yandex_intent", {"text": text})

    async def async_turn_on(self):
        pass

    async def async_turn_off(self):
        pass


# noinspection PyAbstractClass
class YandexMediaPlayer(MediaPlayerEntity, YandexEntity):
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_icon = "mdi:television-classic"

    sources: dict

    def internal_init(self, capabilities: dict, properties: dict):
        if item := capabilities.get("on"):
            if item["retrievable"] is False:
                self._attr_assumed_state = True
                self._attr_state = MediaPlayerState.IDLE

            self._attr_supported_features |= MediaPlayerEntityFeature.TURN_ON
            self._attr_supported_features |= MediaPlayerEntityFeature.TURN_OFF

        if "pause" in capabilities:
            # without play, pause from the interface does not work
            self._attr_supported_features |= MediaPlayerEntityFeature.PLAY
            self._attr_supported_features |= MediaPlayerEntityFeature.PAUSE

        if "volume" in capabilities:
            self._attr_supported_features |= MediaPlayerEntityFeature.VOLUME_STEP

        if "mute" in capabilities:
            self._attr_supported_features |= MediaPlayerEntityFeature.VOLUME_MUTE

        if "channel" in capabilities:
            self._attr_supported_features |= MediaPlayerEntityFeature.NEXT_TRACK
            self._attr_supported_features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
            self._attr_supported_features |= MediaPlayerEntityFeature.PLAY_MEDIA

        if item := capabilities.get("input_source"):
            self.sources = {i["name"]: i["value"] for i in item["modes"]}
            self._attr_source_list = list(self.sources.keys())
            self._attr_supported_features |= MediaPlayerEntityFeature.SELECT_SOURCE

    def internal_update(self, capabilities: dict, properties: dict):
        if (
            "state_template" not in self.config
            and "on" in capabilities
            and not self._attr_assumed_state
        ):
            self._attr_state = (
                MediaPlayerState.ON if capabilities["on"] else MediaPlayerState.OFF
            )

    async def async_added_to_hass(self):
        if item := self.config.get("state_template"):
            on_remove = utils.track_template(self.hass, item, self.on_track_template)
            self.async_on_remove(on_remove)

    def on_track_template(self, value: str):
        try:
            self._attr_assumed_state = False
            self._attr_state = MediaPlayerState(value)
        except:
            self._attr_state = None
        self._async_write_ha_state()

    async def async_turn_on(self):
        await self.quasar.device_actions(self.device["id"], on=True)

    async def async_turn_off(self):
        await self.quasar.device_actions(self.device["id"], on=False)

    async def async_volume_up(self):
        await self.quasar.device_actions(self.device["id"], volume=1)

    async def async_volume_down(self):
        await self.quasar.device_actions(self.device["id"], volume=-1)

    async def async_mute_volume(self, mute):
        await self.quasar.device_actions(self.device["id"], mute=mute)

    async def async_media_next_track(self):
        await self.quasar.device_actions(self.device["id"], channel=1)

    async def async_media_previous_track(self):
        await self.quasar.device_actions(self.device["id"], channel=-1)

    async def async_media_play(self):
        await self.quasar.device_actions(self.device["id"], pause=False)

    async def async_media_pause(self):
        await self.quasar.device_actions(self.device["id"], pause=True)

    async def async_select_source(self, source: str):
        source = self.sources[source]
        await self.quasar.device_actions(self.device["id"], input_source=source)

    async def async_play_media(self, media_type: MediaType, media_id: str, **kwargs):
        if media_type == MediaType.CHANNEL:
            await self.quasar.device_action(self.device["id"], "channel", int(media_id))
