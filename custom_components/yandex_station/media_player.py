import asyncio
import base64
import json
import logging
import re
from typing import Optional

from homeassistant.components.media_player import MediaPlayerDevice, \
    SUPPORT_PAUSE, SUPPORT_VOLUME_SET, SUPPORT_PREVIOUS_TRACK, \
    SUPPORT_NEXT_TRACK, SUPPORT_PLAY, SUPPORT_TURN_OFF, \
    SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_MUTE, SUPPORT_PLAY_MEDIA, \
    SUPPORT_SEEK, SUPPORT_SELECT_SOUND_MODE, SUPPORT_SELECT_SOURCE, \
    DEVICE_CLASS_TV, SUPPORT_TURN_ON
from homeassistant.const import STATE_PLAYING, STATE_PAUSED, STATE_IDLE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt

from . import utils, DOMAIN

_LOGGER = logging.getLogger(__name__)

RE_EXTRA = re.compile(br'{.+[\d"]}')
RE_MUSIC_ID = re.compile(r'^\d+(:\d+)?$')

BASE_FEATURES = (SUPPORT_TURN_OFF | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP |
                 SUPPORT_VOLUME_MUTE | SUPPORT_PLAY_MEDIA |
                 SUPPORT_SELECT_SOUND_MODE | SUPPORT_TURN_ON)

SOUND_MODE1 = "Произнеси текст"
SOUND_MODE2 = "Выполни команду"


# noinspection PyUnusedLocal
def setup_platform(hass, config, add_entities, discovery_info=None):
    if discovery_info is None:
        return

    if DOMAIN in hass.data and discovery_info['platform'] == 'yandexstation':
        quasar = hass.data[DOMAIN]
        quasar_config = quasar.get_device_config(discovery_info)
        add_entities([YandexStationHDMI(discovery_info, quasar_config)])
    else:
        add_entities([YandexStation(discovery_info)])


# noinspection PyAbstractClass
class YandexStation(MediaPlayerDevice, utils.Glagol):
    def __init__(self, config: dict):
        super().__init__()

        self._config = config
        self._name: Optional[str] = None
        self._state: Optional[dict] = None
        self._extra: Optional[dict] = None
        self._updated_at: Optional[dt] = None
        self._prev_volume = None
        self._sound_mode = SOUND_MODE1

    async def async_added_to_hass(self) -> None:
        self._name = self._config['name']

        session = async_get_clientsession(self.hass)
        coro = self.run_forever(session)
        asyncio.create_task(coro)

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def unique_id(self) -> Optional[str]:
        return self._config['id']

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def state(self):
        if self._state:
            if 'playerState' in self._state:
                return STATE_PLAYING if self._state['playing'] \
                    else STATE_PAUSED
            else:
                return STATE_IDLE
        else:
            return None

    @property
    def volume_level(self):
        return self._state['volume'] if self._state else None

    @property
    def is_volume_muted(self):
        return bool(self._prev_volume)

    # @property
    # def media_content_id(self):
    #     return None

    @property
    def media_content_type(self):
        if self._state and 'playerState' in self._state:
            # TODO: right type
            if self._extra and self._extra.get('title') == \
                    self._state['playerState'].get('title'):
                return 'music'
            else:
                return 'video'

        return None

    @property
    def media_duration(self):
        return self._state['playerState']['duration'] \
            if self._state and 'playerState' in self._state else None

    @property
    def media_position(self):
        return self._state['playerState']['progress'] \
            if self._state and 'playerState' in self._state else None

    @property
    def media_position_updated_at(self):
        # TODO: check this
        return self._updated_at

    @property
    def media_image_url(self):
        if self.media_content_type == 'music' and 'ogImage' in self._extra:
            return 'https://' + self._extra['ogImage'].replace('%%', '400x400')

        return None

    @property
    def media_image_remotely_accessible(self) -> bool:
        return True

    @property
    def media_title(self):
        return self._state['playerState']['title'] \
            if self._state and 'playerState' in self._state else None

    @property
    def media_artist(self):
        return self._state['playerState']['subtitle'] \
            if self._state and 'playerState' in self._state else None

    @property
    def supported_features(self):
        features = BASE_FEATURES

        if self._state and 'playerState' in self._state:
            features |= SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_SEEK

            if self._state['playerState']['hasPrev']:
                features |= SUPPORT_PREVIOUS_TRACK
            if self._state['playerState']['hasNext']:
                features |= SUPPORT_NEXT_TRACK

        return features

    @property
    def sound_mode(self):
        return self._sound_mode

    @property
    def sound_mode_list(self):
        return [SOUND_MODE1, SOUND_MODE2]

    @property
    def state_attributes(self):
        attrs = super().state_attributes
        if attrs and self._state:
            attrs['alice_state'] = self._state['aliceState']
        return attrs

    async def async_select_sound_mode(self, sound_mode):
        self._sound_mode = sound_mode

    async def async_mute_volume(self, mute):
        if mute and self.volume_level > 0:
            volume = 0
            self._prev_volume = self.volume_level
        elif not mute and self._prev_volume:
            volume = self._prev_volume
            self._prev_volume = None
        else:
            return

        await self.send_to_station({'command': 'setVolume', 'volume': volume})

    async def async_set_volume_level(self, volume):
        # у станции округление громкости до десятых
        await self.send_to_station({
            'command': 'setVolume',
            'volume': round(volume, 1)
        })

    async def async_media_seek(self, position):
        await self.send_to_station({
            'command': 'rewind',
            'position': position
        })

    async def async_media_play(self):
        await self.send_to_station({'command': 'play'})

    async def async_media_pause(self):
        await self.send_to_station({'command': 'stop'})

    async def async_media_previous_track(self):
        await self.send_to_station({'command': 'prev'})

    async def async_media_next_track(self):
        await self.send_to_station({'command': 'next'})

    async def async_turn_on(self):
        await self.send_to_station(utils.update_form(
            'personal_assistant.scenarios.player_continue'))

    async def async_turn_off(self):
        await self.send_to_station(utils.update_form(
            'personal_assistant.scenarios.quasar.go_home'))

    async def update(self, data: dict = None):
        data['state'].pop('timeSinceLastVoiceActivity', None)

        # _LOGGER.debug(data['state']['aliceState'])

        # skip same state
        if self._state == data['state']:
            return

        self._state = data['state']

        # noinspection PyBroadException
        try:
            data = data['extra']['appState'].encode('ascii')
            data = base64.b64decode(data)
            m = RE_EXTRA.search(data)
            self._extra = json.loads(m[0]) if m else None
        except Exception:
            self._extra = None

        self._updated_at = dt.utcnow()

        # _LOGGER.debug(f"Update state {self._config['id']}")

        self.schedule_update_ha_state()

    async def async_play_media(self, media_type: str, media_id: str, **kwargs):
        if media_type == 'tts':
            media_type = 'text' if self.sound_mode == SOUND_MODE1 \
                else 'command'

        if media_type == 'text':
            payload = {'command': 'sendText',
                       'text': f"Повтори за мной '{media_id}'"}

        elif media_type == 'command':
            payload = {'command': 'sendText', 'text': media_id}

        elif media_type == 'dialog':
            payload = utils.update_form(
                'personal_assistant.scenarios.repeat_after_me',
                request=media_id)

        elif media_type == 'json':
            payload = json.loads(media_id)

        elif RE_MUSIC_ID.match(media_id):
            payload = {'command': 'playMusic', 'id': media_id,
                       'type': media_type}

        else:
            _LOGGER.warning(f"Unsupported media: {media_id}")
            return

        await self.send_to_station(payload)


SOURCE_STATION = 'Станция'
SOURCE_HDMI = 'HDMI'


# noinspection PyAbstractClass
class YandexStationHDMI(YandexStation):
    def __init__(self, config: dict, quasar_config: dict):
        super().__init__(config)

        self._quasar_config = quasar_config

    @property
    def device_class(self) -> Optional[str]:
        return DEVICE_CLASS_TV

    @property
    def supported_features(self):
        return super().supported_features | SUPPORT_SELECT_SOURCE

    @property
    def source(self):
        return SOURCE_HDMI if self._quasar_config.get('hdmiAudio') \
            else SOURCE_STATION

    @property
    def source_list(self):
        return [SOURCE_STATION, SOURCE_HDMI]

    def select_source(self, source):
        quasar = self.hass.data[DOMAIN]

        if source == SOURCE_STATION:
            self._quasar_config.pop('hdmiAudio', None)
        else:
            self._quasar_config['hdmiAudio'] = True

        quasar.set_device_config(self._config, self._quasar_config)
