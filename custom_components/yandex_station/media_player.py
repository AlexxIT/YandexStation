import base64
import json
import logging
import re
from typing import Optional

from homeassistant.components.media_player import MediaPlayerDevice, \
    SUPPORT_PAUSE, SUPPORT_VOLUME_SET, SUPPORT_PREVIOUS_TRACK, \
    SUPPORT_NEXT_TRACK, SUPPORT_PLAY, SUPPORT_TURN_OFF, \
    SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_MUTE, SUPPORT_PLAY_MEDIA, SUPPORT_SEEK, \
    SUPPORT_SELECT_SOUND_MODE, SUPPORT_SELECT_SOURCE
from homeassistant.const import STATE_PLAYING, STATE_PAUSED, \
    STATE_IDLE
from homeassistant.util import dt

from . import utils, DOMAIN

_LOGGER = logging.getLogger(__name__)

RE_EXTRA = re.compile(br'{.+[\d"]}')

BASE_FEATURES = (SUPPORT_TURN_OFF | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP |
                 SUPPORT_VOLUME_MUTE | SUPPORT_PLAY_MEDIA |
                 SUPPORT_SELECT_SOUND_MODE)

SOUND_MODE1 = 'Произнеси текст'
SOUND_MODE2 = 'Выполни команду'


def setup_platform(hass, config, add_entities, discovery_info=None):
    if discovery_info is None:
        return

    if DOMAIN in hass.data and discovery_info['platform'] == 'yandexstation':
        quasar = hass.data[DOMAIN]
        quasar_config = quasar.get_device_config(discovery_info)
        add_entities([YandexStationHDMI(discovery_info, quasar_config)])
    else:
        add_entities([YandexStation(discovery_info)])


class YandexStation(MediaPlayerDevice):
    def __init__(self, config: dict):
        self._config = config
        self._name = None
        self._state = None
        self._extra = None
        self._updated_at = None
        self._prev_volume = 0.1
        self._sound_mode = SOUND_MODE1

    async def async_added_to_hass(self) -> None:
        self._name = self._config['name']

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
        return self._state['volume'] == 0 if self._state else None

    # @property
    # def media_content_id(self):
    #     return None

    @property
    def media_content_type(self):
        # TODO: right type
        if self._state and 'playerState' in self._state:
            return 'music' if self._extra and self._extra['title'] == \
                              self._state['playerState']['title'] else 'video'

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
        return self._updated_at

    @property
    def media_image_url(self):
        if self._extra and self._state and 'playerState' in self._state and \
                self._extra['title'] == self._state['playerState']['title']:
            return 'https://' + self._extra['ogImage'].replace('%%', '400x400')
        else:
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

    async def async_select_sound_mode(self, sound_mode):
        self._sound_mode = sound_mode

    async def async_update(self):
        res = await utils.send_to_station(self._config)
        self._state = res['state']

        res = res['extra']['appState'].encode('ascii')
        res = base64.b64decode(res)
        m = RE_EXTRA.search(res)
        self._extra = json.loads(m[0]) if m else None

        self._updated_at = dt.utcnow()

        _LOGGER.debug(self._extra)

    async def async_mute_volume(self, mute):
        if mute and self.volume_level > 0:
            self._prev_volume = self.volume_level

        await utils.send_to_station(self._config, {
            'command': 'setVolume',
            'volume': 0 if mute else self._prev_volume
        })

    async def async_set_volume_level(self, volume):
        # у станции округление громкости до десятых
        await utils.send_to_station(self._config, {
            'command': 'setVolume',
            'volume': round(volume, 1)
        })

    async def async_media_seek(self, position):
        await utils.send_to_station(self._config, {
            'command': 'rewind',
            'position': position
        })

    async def async_media_play(self):
        await utils.send_to_station(self._config, {'command': 'play'})

    async def async_media_pause(self):
        await utils.send_to_station(self._config, {'command': 'stop'})

    async def async_media_previous_track(self):
        await utils.send_to_station(self._config, {'command': 'prev'})

    async def async_media_next_track(self):
        await utils.send_to_station(self._config, {'command': 'next'})

    async def async_play_media(self, media_type, media_id, **kwargs):
        if media_type == 'text':
            message = f"Повтори за мной '{media_id}'" \
                if self.sound_mode == SOUND_MODE1 else media_id

            await utils.send_to_station(self._config, {
                'command': 'sendText', 'text': message})
        else:
            await utils.send_to_station(self._config, {
                'command': 'playMusic', 'id': media_id, 'type': media_type})

    async def async_turn_off(self):
        await utils.send_to_station(self._config, {
            'command': 'sendText',
            'text': "Главный экран"
        })


SOURCE_STATION = 'Станция'
SOURCE_HDMI = 'HDMI'


class YandexStationHDMI(YandexStation):
    def __init__(self, config: dict, quasar_config: dict):
        super().__init__(config)

        self._quasar_config = quasar_config

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
