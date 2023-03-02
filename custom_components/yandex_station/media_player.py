import base64
import binascii
import json
import logging
import re
import time
import uuid
from datetime import timedelta
from typing import Optional

import yaml
from homeassistant.components import shopping_list
from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_TURN_ON,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_PLAY,
    SUPPORT_PAUSE,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_NEXT_TRACK,
    SUPPORT_SELECT_SOURCE,
    MediaPlayerEntity,
    BrowseMedia,
    MediaPlayerDeviceClass,
    SUPPORT_SEEK,
)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_TVSHOW,
    MEDIA_TYPE_CHANNEL,
    MEDIA_CLASS_APP,
)
from homeassistant.components.media_source.models import BrowseMediaSource
from homeassistant.const import STATE_PLAYING, STATE_PAUSED, STATE_IDLE
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.template import Template
from homeassistant.util import dt

from . import DOMAIN, DATA_CONFIG, CONF_INCLUDE, CONF_INTENTS
from .core import utils
from .core.yandex_glagol import YandexGlagol
from .core.yandex_music import get_mp3
from .core.yandex_quasar import YandexQuasar

_LOGGER = logging.getLogger(__name__)

# update speaker online state once per 5 minutes
SCAN_INTERVAL = timedelta(minutes=5)

RE_EXTRA = re.compile(rb'{".+?}\n')
RE_MUSIC_ID = re.compile(r"^\d+(:\d+)?$")
RE_SHOPPING = re.compile(r"^\d+\) (.+)\.$", re.MULTILINE)

BASE_FEATURES = (
    SUPPORT_TURN_OFF
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_STEP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_TURN_ON
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_BROWSE_MEDIA
)

CLOUD_FEATURES = (
    BASE_FEATURES
    | SUPPORT_PLAY
    | SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
)
LOCAL_FEATURES = BASE_FEATURES | SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_SELECT_SOURCE

SOUND_MODE1 = "Произнеси текст"
SOUND_MODE2 = "Выполни команду"

MEDIA_DEFAULT = [
    {
        "title": "Произнеси текст",
        "media_content_type": "text",
        "thumbnail": "https://brands.home-assistant.io/_/tts/icon.png",
    },
    {
        "title": "Выполни команду",
        "media_content_type": "command",
        "thumbnail": "https://brands.home-assistant.io/_/automation/icon.png",
    },
]

SOURCE_STATION = "Станция"
SOURCE_HDMI = "HDMI"

# Thanks to: https://github.com/iswitch/ha-yandex-icons
CUSTOM = {
    "yandexstation": ["yandex:station", "Яндекс", "Станция"],
    "yandexstation_2": ["yandex:station-max", "Яндекс", "Станция Макс"],
    "yandexmidi": ["yandex:station-2", "Яндекс", "Станция 2"],
    "yandexmini": ["yandex:station-mini", "Яндекс", "Станция Мини"],
    "yandexmini_2": ["yandex:station-mini-2", "Яндекс", "Станция Мини 2"],
    "yandexmicro": ["yandex:station-lite", "Яндекс", "Станция Лайт"],
    "yandexmodule": ["yandex:module", "Яндекс", "Модуль"],
    "yandexmodule_2": ["yandex:module-2", "Яндекс", "Модуль 2"],
    "yandex_tv": ["mdi:television-classic", "Яндекс", "ТВ"],
    "lightcomm": ["yandex:dexp-smartbox", "DEXP", "Smartbox"],
    "elari_a98": ["yandex:elari-smartbeat", "Elari", "SmartBeat"],
    "linkplay_a98": ["yandex:irbis-a", "IRBIS", "A"],
    "wk7y": ["yandex:lg-xboom-wk7y", "LG", "XBOOM AI ThinQ WK7Y"],
    "prestigio_smart_mate": ["yandex:prestigio-smartmate", "Prestigio", "Smartmate"],
    "jbl_link_music": ["yandex:jbl-link-music", "JBL", "Link Music"],
    "jbl_link_portable": ["yandex:jbl-link-portable", "JBL", "Link Portable"],
}

DEVICES = ["devices.types.media_device.tv"]


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
        QuasarTV(quasar, device)
        for device in quasar.devices
        if device["name"] in include and device["type"] in DEVICES
    ]
    async_add_entities(entities, True)


# noinspection PyUnusedLocal
def setup_platform(hass, config, add_entities, discovery_info=None):
    # only intents setup via setup platform
    intents = discovery_info[CONF_INTENTS]
    add_entities([YandexIntents(intents)])


# noinspection PyAbstractClass
class YandexSource(BrowseMediaSource):
    def __init__(self, **kwargs):
        query = {}
        if kwargs.get("media_content_id"):
            query["message"] = kwargs.pop("media_content_id")
            kwargs.setdefault("can_expand", False)
        if kwargs.get("template"):
            query["template"] = template = kwargs.pop("template")
            kwargs.setdefault("can_expand", "message" in template)
        if kwargs.get("extra"):
            extra = kwargs.pop("extra")
            query["volume_level"] = extra["volume_level"]
        if query:
            kwargs["identifier"] = utils.encode_media_source(query)

        kwargs = {
            "domain": "tts",  # will show message/say dialog
            "identifier": DOMAIN,  # may be any but not empty
            "media_class": MEDIA_CLASS_APP,  # needs for icon
            "can_play": False,  # show play button in
            "can_expand": True,  # true - show say dialog, false - run command
            **kwargs,  # override all default values
        }
        super().__init__(**kwargs)


# noinspection PyAbstractClass
class MediaBrowser(MediaPlayerEntity):
    media_cache: list = None

    async def async_browse_media(
        self,
        media_content_type: str = None,
        media_content_id: str = None,
    ) -> BrowseMedia:
        if not MediaBrowser.media_cache:
            conf = self.hass.data[DOMAIN][DATA_CONFIG]
            conf = conf.get("media_source") or MEDIA_DEFAULT
            MediaBrowser.media_cache = [YandexSource(**item) for item in conf]

        for media in MediaBrowser.media_cache:
            if (
                media.media_content_id == media_content_id
                and media.media_content_type == media_content_type
            ):
                return media

        return BrowseMediaSource(
            title=self.name,
            children=MediaBrowser.media_cache,
            domain=None,
            identifier=None,
            media_class=None,
            media_content_type=None,
            can_play=False,
            can_expand=True,
        )


# noinspection PyAbstractClass
class YandexStation(MediaBrowser):
    _attr_extra_state_attributes: dict = None

    local_state: Optional[dict] = None
    # для управления громкостью Алисы
    alice_volume: Optional[dict] = None

    # true of false if device has HDMI
    hdmi_audio: Optional[bool] = None

    # song_id to know when sond changes
    sync_id: Optional[str] = None
    # for disabling mute when speak with Alice
    sync_mute: Optional[bool] = None
    # {name: entity_id} pairs
    sync_sources: dict = None
    # if sync mode enabled
    sync_state: Optional[bool] = None
    sync_volume: Optional[float] = None

    glagol: YandexGlagol = None

    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device
        self.requests = {}

        self._attr_assumed_state = True
        self._attr_extra_state_attributes = {}
        self._attr_is_volume_muted = False
        self._attr_media_image_remotely_accessible = True
        self._attr_name = device["name"]
        self._attr_should_poll = True
        self._attr_state = STATE_IDLE
        self._attr_sound_mode_list = [SOUND_MODE1, SOUND_MODE2]
        self._attr_sound_mode = SOUND_MODE1
        self._attr_supported_features = CLOUD_FEATURES
        self._attr_volume_level = 0.5
        self._attr_unique_id = device["quasar_info"]["device_id"]

        self._attr_device_info = info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.device["name"],
        )
        if self.device_platform in CUSTOM:
            info["manufacturer"] = CUSTOM[self.device_platform][1]
            info["model"] = CUSTOM[self.device_platform][2]

        # backward compatibility
        self.entity_id = "media_player."
        if self.device_platform.startswith("yandexmodule"):
            self.entity_id += "yandex_module"
        elif self.device_platform.startswith("yandex_tv"):
            self.entity_id += "yandex_tv"
        else:
            self.entity_id += "yandex_station"
        self.entity_id += "_" + self._attr_unique_id.lower()

    # ADDITIONAL CLASS FUNCTION

    @property
    def device_platform(self) -> str:
        platform: str = self.device["quasar_info"]["platform"]
        if platform == "goya" or platform.startswith("yandex_tv"):
            platform = "yandex_tv"
        return platform

    def debug(self, text: str):
        _LOGGER.debug(f"{self.name} | {text}")

    async def init_local_mode(self):
        # self.debug(f"Init local mode (hass: {self.hass is not None})")
        if not self.glagol:
            self.glagol = YandexGlagol(self.quasar.session, self.device)
            self.glagol.update_handler = self.async_set_state

        await self.glagol.start_or_restart()

        # init sources only once
        if self.sync_sources is not None:
            return

        self.sync_sources = {
            src["name"]: src
            for src in utils.get_media_players(self.hass, self.entity_id)
        }

        # for HomeKit source list support
        self._attr_device_class = MediaPlayerDeviceClass.TV
        self._attr_source_list = [SOURCE_STATION] + list(self.sync_sources.keys())
        self._attr_source = SOURCE_STATION

        await self.init_hdmi_audio()

    async def init_hdmi_audio(self):
        if self.device_platform not in ("yandexstation", "yandexstation_2"):
            return

        # load state if unknown
        if self.hdmi_audio is None:
            try:
                conf = await self.quasar.get_device_config(self.device)
                self.hdmi_audio = conf.get("hdmiAudio", False)
            except:
                _LOGGER.warning("Не получается получить настройки HDMI")
                return

        if self.hdmi_audio:
            self._attr_source = SOURCE_HDMI
        self._attr_source_list.insert(1, SOURCE_HDMI)

    async def sync_hdmi_audio(self):
        # if HDMI supported and state loaded
        if self.hdmi_audio is None:
            return

        if self._attr_source == SOURCE_STATION:
            enabled = False
        elif self._attr_source == SOURCE_HDMI:
            enabled = True
        else:
            return

        # check if something changed
        if self.hdmi_audio == enabled:
            return

        try:
            device_config = await self.quasar.get_device_config(self.device)
            if enabled:
                device_config["hdmiAudio"] = True
            else:
                device_config.pop("hdmiAudio", None)
            await self.quasar.set_device_config(self.device, device_config)
        except:
            _LOGGER.warning("Не получается изменить настройки HDMI")
            return

        self.hdmi_audio = enabled

    async def response(self, card: dict, request_id: str):
        if not card:
            self.debug(f"Empty response on request: {request_id}")
            return

        self.debug(f"{card['text']} | {request_id}")

        if card["type"] == "simple_text":
            text = card["text"]

        elif card["type"] == "text_with_button":
            text = card["text"]

            for button in card["buttons"]:
                assert button["type"] == "action"
                for directive in button["directives"]:
                    if directive["name"] == "open_uri":
                        title = button["title"]
                        uri = directive["payload"]["uri"]
                        text += f"\n[{title}]({uri})"

        else:
            _LOGGER.error(f"Неизвестный тип ответа: {card['type']}")
            return

        self.hass.bus.async_fire(
            f"{DOMAIN}_response",
            {
                "entity_id": self.entity_id,
                "name": self.name,
                "text": text,
                "request_id": request_id,
            },
        )

    async def _set_brightness(self, value: str):
        if self.device_platform not in ("yandexstation_2", "yandexmini_2"):
            _LOGGER.warning("Поддерживаются только станции с экраном")
            return

        device_config = await self.quasar.get_device_config(self.device)
        if not device_config:
            _LOGGER.warning("Не получается получить настройки станции")
            return

        try:
            value = float(value)
        except:
            _LOGGER.exception(f"Недопустимое значение яркости: {value}")
            return

        if "led" not in device_config:
            device_config["led"] = {"brightness": {"auto": True, "value": 0.5}}

        if 0 <= value <= 1:
            device_config["led"]["brightness"]["auto"] = False
            device_config["led"]["brightness"]["value"] = value
        else:
            device_config["led"]["brightness"]["auto"] = True

        await self.quasar.set_device_config(self.device, device_config)

    async def _set_beta(self, value: str):
        device_config = await self.quasar.get_device_config(self.device)

        if value == "True":
            value = True
        elif value == "False":
            value = False
        else:
            value = None

        if value is not None:
            device_config["beta"] = value
            await self.quasar.set_device_config(self.device, device_config)

        self.hass.components.persistent_notification.async_create(
            f"{self.name} бета-тест: {device_config['beta']}"
        )

    async def _set_settings(self, value: str):
        data = yaml.safe_load(value)
        for k, v in data.items():
            await self.quasar.set_account_config(k, v)

    async def _shopping_list(self):
        if shopping_list.DOMAIN not in self.hass.data:
            return

        data: shopping_list.ShoppingData = self.hass.data[shopping_list.DOMAIN]

        card = await self.glagol.send(
            {"command": "sendText", "text": "Что в списке покупок"}
        )
        alice_list = RE_SHOPPING.findall(card["text"])
        self.debug(f"Список покупок: {alice_list}")

        remove_from = [
            alice_list.index(item["name"])
            for item in data.items
            if item["complete"] and item["name"] in alice_list
        ]
        if remove_from:
            # не может удалить больше 6 штук за раз
            remove_from = sorted(remove_from, reverse=True)
            for i in range(0, len(remove_from), 6):
                items = [str(p + 1) for p in remove_from[i : i + 6]]
                text = "Удали из списка покупок: " + ", ".join(items)
                await self.glagol.send({"command": "sendText", "text": text})

        add_to = [
            item["name"]
            for item in data.items
            if not item["complete"]
            and item["name"] not in alice_list
            and not item["id"].startswith("alice")
        ]
        for name in add_to:
            # плохо работает, если добавлять всё сразу через запятую
            text = "Добавь в список покупок " + name
            await self.glagol.send({"command": "sendText", "text": text})

        if add_to or remove_from:
            card = await self.glagol.send(
                {"command": "sendText", "text": "Что в списке покупок"}
            )
            alice_list = RE_SHOPPING.findall(card["text"])
            self.debug(f"Новый список покупок: {alice_list}")

        data.items = [
            {"name": name, "id": "alice" + uuid.uuid4().hex, "complete": False}
            for name in alice_list
        ]
        await self.hass.async_add_executor_job(data.save)

    async def _sync_play_media(self, player_state: dict):
        self.debug(f"Sync state: play_media")

        url = await get_mp3(self.quasar.session, player_state)
        if not url:
            return

        await self.async_media_seek(0)

        source = self.sync_sources[self._attr_source]
        data = {
            "media_content_id": utils.StreamingView.get_url(
                self.hass, self._attr_unique_id, url
            ),
            "media_content_type": source.get("media_content_type", "music"),
            "entity_id": source["entity_id"],
        }

        await self.hass.services.async_call("media_player", "play_media", data)

    def _check_set_alice_volume(self, volume: int):
        # если уже есть активная громкость, или громкость голоса равна текущей
        # громкости колонки - ничего не делаем
        if self.alice_volume or volume == self.volume_level:
            return

        self.alice_volume = {
            "prev_volume": self.volume_level,
            "wait_state": "SPEAKING",
            "wait_ts": time.time() + 30,
        }

        self.hass.create_task(self.async_set_volume_level(volume))

    def _process_alice_volume(self, alice_state: str):
        volume = None

        # если что-то пошло не так, через 30 секунд возвращаем громкость
        if time.time() > self.alice_volume["wait_ts"]:
            if "prev_volume" in self.alice_volume:
                volume = self.alice_volume["prev_volume"]
            self.alice_volume = None

        elif self.alice_volume["wait_state"] == alice_state:
            if alice_state == "SPEAKING":
                self.alice_volume["wait_state"] = "IDLE"

            elif alice_state == "IDLE":
                volume = self.alice_volume["prev_volume"]
                self.alice_volume = None

        if volume:
            self.hass.create_task(self.async_set_volume_level(volume))

    @callback
    def yandex_dialog(self, media_type: str, media_id: str):
        """Passes TTS data to YandexDialogs component and return text command to
        start dialog with data CRC-hash as ID.
        """
        if media_type.startswith("dialog"):
            _, name, tag = media_type.split(":")
            payload = {
                "tts": media_id,
                "session": {"dialog": tag},
                "end_session": False,
            }
        else:
            _, name = media_type.split(":")
            payload = {"tts": media_id}

        crc = str(binascii.crc32(f"{self.entity_id}.{media_id}".encode()))
        try:
            dialog = self.hass.data["yandex_dialogs"]
            dialog.dialogs[crc] = payload
        except:
            _LOGGER.warning("Компонент Яндекс Диалогов не подключен")

        return f"СКАЖИ НАВЫКУ {name} {crc}"

    @callback
    def async_sync_state(self, service: str, **kwargs):
        self.debug(f"Sync state: {service}")

        source = self.sync_sources[self._attr_source]
        if source.get("sync_volume") is False and service == "volume_set":
            return

        if service == "play_media":
            self.hass.async_create_task(self.async_media_seek(0))
            kwargs["media_content_id"] = utils.StreamingView.get_url(
                self.hass, self._attr_unique_id, kwargs.pop("url")
            )
            kwargs["media_content_type"] = source.get("media_content_type", "music")

        kwargs["entity_id"] = source["entity_id"]

        self.hass.async_create_task(
            self.hass.services.async_call("media_player", service, kwargs)
        )

    @callback
    def update_device_info(self, sw_version: str):
        if not self.hass:
            return
        registry: DeviceRegistry = self.hass.data["device_registry"]
        device = registry.async_get_device({(DOMAIN, self._attr_unique_id)}, None)
        registry.async_update_device(device.id, sw_version=sw_version)

    @callback
    def async_set_state(self, data: dict):
        if data is None:
            self.debug("Возврат в облачный режим")
            self.local_state = None

            self._attr_assumed_state = True
            self._attr_extra_state_attributes.pop("alice_state", None)
            self._attr_media_artist = None
            self._attr_media_content_type = None
            self._attr_media_duration = None
            self._attr_media_image_url = None
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
            self._attr_media_title = None
            self._attr_supported_features = CLOUD_FEATURES
            self._attr_should_poll = True

            self.async_write_ha_state()
            return

        is_send_by_speaker = "requestId" not in data

        state = data["state"]
        state["local_push"] = is_send_by_speaker
        state.pop("timeSinceLastVoiceActivity", None)

        # skip same state
        if self.local_state == state:
            return

        if "softwareVersion" in data:
            self.update_device_info(data["softwareVersion"])

        self.local_state = state

        # возвращаем из состояния mute, если нужно
        # if self.prev_volume and state['volume']:
        #     self.prev_volume = None

        if self.alice_volume:
            self._process_alice_volume(state["aliceState"])

        extra_item = extra_stream = None

        try:
            astate = data["extra"]["appState"].encode("ascii")
            astate = base64.b64decode(astate)
            for m in RE_EXTRA.findall(astate):
                m = json.loads(m)
                if "item" in m:
                    extra_item = m["item"]
                if "stream" in m:
                    extra_stream = m["stream"]
        except:
            pass

        mctp = miur = mpos = mart = mdur = mtit = None
        stat = STATE_IDLE
        spft = LOCAL_FEATURES

        # в прошивке Яндекс.Станции Мини есть косяк - звук всегда (int) 0
        vlvl = state["volume"] if isinstance(state["volume"], float) else None

        pstate = state.get("playerState")
        if pstate:
            try:
                if pstate.get("liveStreamText") == "Прямой эфир":
                    mctp = MEDIA_TYPE_CHANNEL  # radio
                elif pstate["extra"]:
                    # music, podcast also shows as music
                    mctp = pstate["extra"]["stateType"]
                elif extra_item:
                    extra_type = extra_item["type"]
                    mctp = (
                        MEDIA_TYPE_TVSHOW
                        if extra_type == "tv_show_episode"
                        else extra_type
                    )
            except:
                pass

            try:
                if pstate["extra"].get("stateType") in ("music", "radio"):
                    url = pstate["extra"]["coverURI"]
                    if url:
                        miur = "https://" + url.replace("%%", "400x400")
                elif extra_item:
                    miur = extra_item["thumbnail_url_16x9"]
            except:
                pass

            mdur = pstate["duration"]
            mpos = pstate["progress"]
            mart = pstate["subtitle"]
            mtit = pstate["title"]

            stat = STATE_PLAYING if state["playing"] else STATE_PAUSED
            if pstate["hasPrev"]:
                spft |= SUPPORT_PREVIOUS_TRACK
            if pstate["hasNext"]:
                spft |= SUPPORT_NEXT_TRACK
            if pstate["duration"]:
                spft |= SUPPORT_SEEK

            if self.sync_state:
                # синхронизируем статус, если выбран такой режим
                if self.sync_state != stat:
                    # синхронизируем статус, если он не совпадает
                    if stat == STATE_PLAYING:
                        if self.sync_id != pstate["id"]:
                            # запускаем новую песню, если ID изменился
                            self.hass.create_task(self._sync_play_media(pstate))
                            self.sync_id = pstate["id"]
                        else:
                            # продолжаем играть, если ID не изменился
                            self.async_sync_state("media_play")

                    else:
                        # останавливаем, если ничего не играет
                        self.async_sync_state("media_pause")

                    self.sync_state = stat

                if self.sync_state == STATE_PLAYING:
                    if vlvl and self.sync_volume != vlvl:
                        self.sync_mute = None
                        self.sync_volume = vlvl
                        self.async_sync_state("volume_set", volume_level=vlvl)

                    # если музыка играет - глушим колонку Яндекса
                    if self.sync_mute is True:
                        # включаем громкость колонки, когда с ней разговариваем
                        if state["aliceState"] != "IDLE":
                            self.sync_mute = False
                            self.hass.create_task(self.async_mute_volume(False))
                    else:
                        # выключаем громкость колонки, когда с ней не
                        # разговариваем
                        if state["aliceState"] == "IDLE":
                            self.sync_mute = True
                            self.hass.create_task(self.async_mute_volume(True))

        self._attr_assumed_state = False
        self._attr_available = True
        self._attr_media_artist = mart
        self._attr_media_content_type = mctp
        self._attr_media_duration = mdur
        self._attr_media_image_url = miur
        self._attr_media_position = mpos
        self._attr_media_position_updated_at = dt.utcnow()  # TODO: check this
        self._attr_media_title = mtit
        self._attr_state = stat
        self._attr_supported_features = spft
        self._attr_should_poll = False

        if vlvl is not None:
            if vlvl > 0:
                self._attr_is_volume_muted = False
                self._attr_volume_level = vlvl
            else:
                self._attr_is_volume_muted = True

        self._attr_extra_state_attributes["alice_state"] = state["aliceState"]

        if self.hass:
            self.async_write_ha_state()

    # BASE MEDIA PLAYER FUNCTIONS

    async def async_added_to_hass(self):
        if await utils.has_custom_icons(self.hass) and self.device_platform in CUSTOM:
            self._attr_icon = CUSTOM[self.device_platform][0]
            self.debug(f"Установка кастомной иконки: {self._attr_icon}")

        if "host" in self.device:
            await self.init_local_mode()

    async def async_will_remove_from_hass(self):
        if self.glagol:
            await self.glagol.stop()

    async def async_select_sound_mode(self, sound_mode: str):
        self._attr_sound_mode = sound_mode
        self.async_write_ha_state()

    async def async_select_source(self, source):
        self.debug(f"Change source to {source}")
        if self.sync_mute is True:
            # включаем звук колонке, если выключали его
            self.hass.create_task(self.async_mute_volume(False))

        if self.sync_state:
            # сбрасываем синхронизацию
            self.sync_state = self.sync_id = self.sync_volume = self.sync_mute = None
            # останавливаем внешний медиаплеер
            self.async_sync_state("media_pause")

        self.sync_state = self.sync_sources and source in self.sync_sources

        self._attr_source = source
        self.async_write_ha_state()

        await self.sync_hdmi_audio()

    async def async_mute_volume(self, mute: bool):
        volume = 0 if mute else self._attr_volume_level
        await self.async_set_volume_level(volume)

    async def async_set_volume_level(self, volume: float):
        # https://github.com/AlexxIT/YandexStation/issues/324
        if isinstance(volume, str):
            try:
                volume = float(volume)
            except Exception:
                return

        if self.local_state:
            # у станции округление громкости до десятых
            await self.glagol.send({"command": "setVolume", "volume": round(volume, 1)})

        else:
            await self.quasar.send(self.device, f"громкость на {round(10 * volume)}")
            if volume > 0:
                self._attr_is_volume_muted = False
                self._attr_volume_level = round(volume, 2)
            else:
                # don't change volume_level so can back to previous value
                self._attr_is_volume_muted = True
            self.async_write_ha_state()

    async def async_media_seek(self, position):
        if self.local_state:
            await self.glagol.send({"command": "rewind", "position": position})

    async def async_media_play(self):
        if self.local_state:
            await self.glagol.send({"command": "play"})

        else:
            await self.quasar.send(self.device, "продолжить")
            self._attr_state = STATE_PLAYING
            self.async_write_ha_state()

    async def async_media_pause(self):
        if self.local_state:
            await self.glagol.send({"command": "stop"})

        else:
            await self.quasar.send(self.device, "пауза")
            self._attr_state = STATE_PAUSED
            self.async_write_ha_state()

    async def async_media_stop(self):
        await self.async_media_pause()

    async def async_media_previous_track(self):
        if self.local_state:
            await self.glagol.send({"command": "prev"})
        else:
            await self.quasar.send(self.device, "прошлый трек")

    async def async_media_next_track(self):
        if self.local_state:
            await self.glagol.send({"command": "next"})
        else:
            await self.quasar.send(self.device, "следующий трек")

    async def async_turn_on(self):
        if self.local_state:
            await self.glagol.send(
                utils.update_form("personal_assistant.scenarios.player_continue")
            )
        else:
            await self.async_media_play()

    async def async_turn_off(self):
        if self.local_state:
            await self.glagol.send(
                utils.update_form("personal_assistant.scenarios.quasar.go_home")
            )
        else:
            await self.async_media_pause()

    async def async_update(self):
        # update online only while cloud connected
        if self.local_state:
            return
        await self.quasar.update_online_stats()
        self._attr_available = self.device.get("online", False)

    async def async_play_media(
        self, media_type: str, media_id: str, extra: dict = None, **kwargs
    ):
        # backward support Hass lower than v2022.3
        if "/api/tts_proxy/" in media_id:
            session = async_get_clientsession(self.hass)
            media_id = await utils.get_tts_message(session, media_id)
            media_type = "tts"

        if media_id.startswith("media-source://tts/"):
            query = utils.decode_media_source(media_id)
            if query.get("template"):
                template = Template(query.pop("template"), self.hass)
                media_id = template.async_render(query)
            else:
                media_id = query["message"]
            if query.get("volume_level"):
                extra.setdefault("volume_level", float(query["volume_level"]))
            # provider, music - from 3rd party TTS (ex google)
            if media_type in ("provider", "music"):
                media_type = "text"

        if not media_id:
            _LOGGER.warning(f"Получено пустое media_id")
            return

        # tts for backward compatibility and mini-media-player support
        if media_type == "tts":
            if self._attr_sound_mode == SOUND_MODE1:
                media_type = "text"
            else:
                media_type = "command"
        elif media_type == "brightness":
            await self._set_brightness(media_id)
            return
        elif media_type == "beta":
            await self._set_beta(media_id)
            return
        elif media_type == "settings":
            await self._set_settings(media_id)
            return

        if self.local_state:
            if "https://" in media_id or "http://" in media_id:
                session = async_get_clientsession(self.hass)
                payload = await utils.get_media_payload(media_id, session)
                if not payload:
                    _LOGGER.warning(f"Unsupported url: {media_id}")
                    return

            elif media_type.startswith(("text:", "dialog:")):
                payload = {
                    "command": "sendText",
                    "text": self.yandex_dialog(media_type, media_id),
                }

            elif media_type == "text":
                # даже в локальном режиме делам TTS через облако, чтоб колонка
                # не продолжала слушать
                force_local: bool = extra and extra.get("force_local")
                if self.quasar.session.x_token and not force_local:
                    media_id = utils.fix_cloud_text(media_id)
                    if extra and extra.get("volume_level") is not None:
                        self._check_set_alice_volume(extra["volume_level"])
                    await self.quasar.send(self.device, media_id, is_tts=True)
                    return

                else:
                    payload = {
                        "command": "sendText",
                        "text": f"Повтори за мной '{media_id}'",
                    }

            elif media_type == "command":
                payload = {"command": "sendText", "text": media_id}

            elif media_type == "dialog":
                if extra and extra.get("volume_level") is not None:
                    self._check_set_alice_volume(extra["volume_level"])
                payload = utils.update_form(
                    "personal_assistant.scenarios.repeat_after_me", request=media_id
                )

            elif media_type == "json":
                payload = json.loads(media_id)

            elif RE_MUSIC_ID.match(media_id):
                payload = {"command": "playMusic", "id": media_id, "type": media_type}

            elif media_type == "shopping_list":
                await self._shopping_list()
                return

            elif media_type.startswith("question"):
                request_id = media_type.split(":", 1)[1] if ":" in media_type else None
                card = await self.glagol.send({"command": "sendText", "text": media_id})
                await self.response(card, request_id)
                return

            else:
                _LOGGER.warning(f"Unsupported local media: {media_id}")
                return

            await self.glagol.send(payload)

        else:
            if media_type.startswith(("text:", "dialog:")):
                media_id = self.yandex_dialog(media_type, media_id)
                await self.quasar.send(self.device, media_id)

            elif media_type == "text":
                media_id = utils.fix_cloud_text(media_id)
                await self.quasar.send(self.device, media_id, is_tts=True)

            elif media_type == "command":
                media_id = utils.fix_cloud_text(media_id)
                await self.quasar.send(self.device, media_id)

            elif media_type == "brightness":
                await self._set_brightness(media_id)
                return

            else:
                _LOGGER.warning(f"Unsupported cloud media: {media_type}")
                return


# noinspection PyAbstractClass
class YandexModule(YandexStation):
    """YandexModule support only local control."""

    def __init__(self, quasar: YandexQuasar, device: dict):
        super().__init__(quasar, device)

        self._attr_available = False
        self._attr_should_poll = False

        # both yandex moduls don't support music sync
        if self.device_platform == "yandexmodule":
            self.sync_sources = {}

        try:
            self.support_on = any(
                cap["state"]["instance"] == "on" for cap in self.device["capabilities"]
            )
        except Exception:
            self.support_on = False

    def async_set_state(self, data: dict):
        super().async_set_state(data)

        if self._attr_available and self.local_state is None:
            self._attr_available = False

    async def async_set_volume_level(self, volume: float):
        if self.device_platform != "yandexmodule":
            volume *= 10
        await super().async_set_volume_level(volume)

    async def async_update(self):
        pass

    async def async_media_play(self):
        if self.device_platform != "yandexmodule":
            await self.glagol.send({"command": "sendText", "text": "продолжить"})
        else:
            await super().async_media_play()

    async def async_play_media(self, media_type: str, media_id: str, **kwargs):
        kwargs["extra"].setdefault("force_local", True)
        await super().async_play_media(media_type, media_id, **kwargs)

    async def async_turn_on(self):
        if self.support_on:
            await self.quasar.device_action(self.device["id"], on=True)
        else:
            await super().async_turn_on()

    async def async_turn_off(self):
        if self.support_on:
            await self.quasar.device_action(self.device["id"], on=False)
        else:
            await super().async_turn_on()


# noinspection PyAbstractClass
class YandexIntents(MediaPlayerEntity):
    def __init__(self, intents: list):
        self.intents = intents

    @property
    def name(self):
        return "Yandex Intents"

    @property
    def supported_features(self):
        return (
            SUPPORT_TURN_ON
            | SUPPORT_TURN_OFF
            | SUPPORT_VOLUME_SET
            | SUPPORT_VOLUME_STEP
        )

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
class QuasarTV(MediaPlayerEntity):
    _sources = None
    _supported_features = 0

    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device

    @property
    def unique_id(self):
        return self.device["id"].replace("-", "")

    @property
    def name(self):
        return self.device["name"]

    @property
    def should_poll(self):
        return False

    @property
    def device_class(self):
        return MediaPlayerDeviceClass.TV

    @property
    def icon(self):
        return "mdi:television-classic"

    @property
    def state(self):
        return STATE_PLAYING

    @property
    def supported_features(self):
        return self._supported_features

    @property
    def source_list(self):
        return list(self._sources.keys())

    async def async_turn_on(self):
        await self.quasar.device_action(self.device["id"], on=True)

    async def async_turn_off(self):
        await self.quasar.device_action(self.device["id"], on=False)

    async def async_volume_up(self):
        await self.quasar.device_action(self.device["id"], volume=1)

    async def async_volume_down(self):
        await self.quasar.device_action(self.device["id"], volume=-1)

    async def async_mute_volume(self, mute):
        await self.quasar.device_action(self.device["id"], mute=mute)

    async def async_media_next_track(self):
        await self.quasar.device_action(self.device["id"], channel=1)

    async def async_media_previous_track(self):
        await self.quasar.device_action(self.device["id"], channel=-1)

    async def async_media_pause(self):
        await self.quasar.device_action(self.device["id"], pause=True)

    async def async_select_source(self, source):
        source = self._sources[source]
        await self.quasar.device_action(self.device["id"], input_source=source)

    async def async_added_to_hass(self):
        data = await self.quasar.get_device(self.device["id"])
        for capability in data["capabilities"]:
            instance = capability["parameters"].get("instance")
            if capability["type"] == "devices.capabilities.on_off":
                self._supported_features |= SUPPORT_TURN_ON | SUPPORT_TURN_OFF
            elif instance == "volume":
                self._supported_features |= SUPPORT_VOLUME_STEP
            elif instance == "channel":
                self._supported_features |= SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK
            elif instance == "input_source":
                self._sources = {
                    p["name"]: p["value"] for p in capability["parameters"]["modes"]
                }
                self._supported_features |= SUPPORT_SELECT_SOURCE
            elif instance == "mute":
                self._supported_features |= SUPPORT_VOLUME_MUTE
            elif instance == "pause":
                # without play, pause from the interface does not work
                self._supported_features |= SUPPORT_PAUSE | SUPPORT_PLAY
