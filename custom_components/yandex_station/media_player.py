import asyncio
import base64
import json
import logging
import re
import uuid
from typing import Optional

from homeassistant.components.media_player import SUPPORT_PAUSE, \
    SUPPORT_VOLUME_SET, SUPPORT_PREVIOUS_TRACK, \
    SUPPORT_NEXT_TRACK, SUPPORT_PLAY, SUPPORT_TURN_OFF, \
    SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_MUTE, SUPPORT_PLAY_MEDIA, \
    SUPPORT_SEEK, SUPPORT_SELECT_SOUND_MODE, SUPPORT_TURN_ON, DEVICE_CLASS_TV, \
    SUPPORT_SELECT_SOURCE
from homeassistant.const import STATE_PLAYING, STATE_PAUSED, STATE_IDLE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt

from . import utils, DOMAIN
from .yandex_glagol import Glagol

try:  # поддержка старых версий Home Assistant
    from homeassistant.components.media_player import MediaPlayerEntity
except:
    from homeassistant.components.media_player import \
        MediaPlayerDevice as MediaPlayerEntity

_LOGGER = logging.getLogger(__name__)

RE_EXTRA = re.compile(br'{.+[\d"]}')
RE_MUSIC_ID = re.compile(r'^\d+(:\d+)?$')

BASE_FEATURES = (SUPPORT_TURN_OFF | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP |
                 SUPPORT_VOLUME_MUTE | SUPPORT_PLAY_MEDIA |
                 SUPPORT_SELECT_SOUND_MODE | SUPPORT_TURN_ON)

SOUND_MODE1 = "Произнеси текст"
SOUND_MODE2 = "Выполни команду"

EXCEPTION_100 = Exception("Нельзя произнести более 100 симоволов :(")

# Thanks to: https://github.com/iswitch/ha-yandex-icons
CUSTOM_ICONS = {
    'yandexstation': 'yandex:station',
    'yandexmini': 'yandex:station-mini',
    'lightcomm': 'yandex:dexp-smartbox',
    'linkplay_a98': 'yandex:irbis-a',
    'elari_a98': 'yandex:elari-smartbeat',
    'wk7y': 'yandex:lg-xboom-wk7y',
    'prestigio_smart_mate': 'yandex:prestigio-smartmate',
    'yandexmodule': 'yandex:module',
}


# noinspection PyUnusedLocal
def setup_platform(hass, config, add_entities, discovery_info=None):
    if isinstance(discovery_info, str):
        device = next(d for d in hass.data[DOMAIN]['devices']
                      if d['device_id'] == discovery_info)

        if 'entity' in device:
            return

        quasar = hass.data[DOMAIN]['quasar']

        device['entity'] = entity = YandexStationHDMI(quasar, device) \
            if device['platform'] == 'yandexstation' \
            else YandexStation(quasar, device)
        add_entities([entity])

    else:
        add_entities([YandexIntents(discovery_info)])


# noinspection PyAbstractClass
class YandexStation(MediaPlayerEntity, Glagol):
    # имя колонки, есть в обоих режимах
    _name: Optional[str] = None
    # режим звука, есть в обоих режимах
    _sound_mode = SOUND_MODE1
    # кастомная иконка
    _icon = None

    # экстра есть только в локальном режиме
    local_extra: Optional[dict] = None
    # время обновления состояния (для ползунка), есть только в локальном режиме
    local_updated_at = None
    # прошлая громкость для правильного mute, есть в обоих режимах
    prev_volume = None

    # облачное состояние, должно быть null, когда появляется локальное
    cloud_state = STATE_IDLE
    # облачный звук
    cloud_volume = .5

    # запросы к станции
    requests = {}

    async def async_added_to_hass(self) -> None:
        # TODO: проверить смену имени!!!
        self._name = self.device['name']

        if await utils.has_custom_icons(self.hass):
            self._icon = CUSTOM_ICONS.get(self.device['platform'])
            _LOGGER.debug(f"Установка кастомной иконки: {self._icon}")

        if 'host' in self.device:
            await self.init_local_mode()

    async def init_local_mode(self):
        if not self.hass:
            return

        session = async_get_clientsession(self.hass)
        asyncio.create_task(self.local_start(session))

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def unique_id(self) -> Optional[str]:
        return self.device['device_id']

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def state(self):
        if self.local_state:
            if 'playerState' in self.local_state:
                return STATE_PLAYING if self.local_state['playing'] \
                    else STATE_PAUSED
            else:
                return STATE_IDLE

        elif self.cloud_state:
            return self.cloud_state

        else:
            return None

    @property
    def icon(self):
        return self._icon

    @property
    def volume_level(self):
        # в прошивке Яндекс.Станции Мини есть косяк - звук всегда (int) 0
        if self.local_state and isinstance(self.local_state['volume'], float):
            return self.local_state['volume']
        else:
            return self.cloud_volume

    @property
    def is_volume_muted(self):
        return bool(self.prev_volume)

    # @property
    # def media_content_id(self):
    #     return None

    @property
    def media_content_type(self):
        if self.local_state and 'playerState' in self.local_state:
            # TODO: right type
            if self.local_extra and self.local_extra.get('title') == \
                    self.local_state['playerState'].get('title'):
                return 'music'
            else:
                return 'video'

        return None

    @property
    def media_duration(self):
        if self.local_state and 'playerState' in self.local_state:
            return self.local_state['playerState']['duration']
        else:
            return None

    @property
    def media_position(self):
        if self.local_state and 'playerState' in self.local_state:
            return self.local_state['playerState']['progress']
        else:
            return None

    @property
    def media_position_updated_at(self):
        # TODO: check this
        return self.local_updated_at

    @property
    def media_image_url(self):
        # local mode checked in media_content_type
        if (self.media_content_type == 'music' and
                self.local_extra.get('ogImage')):
            url = self.local_extra['ogImage'].replace('%%', '400x400')
            return 'https://' + url

        return None

    @property
    def media_image_remotely_accessible(self) -> bool:
        return True

    @property
    def media_title(self):
        if self.local_state and 'playerState' in self.local_state:
            return self.local_state['playerState']['title']
        else:
            return None

    @property
    def media_artist(self):
        if self.local_state and 'playerState' in self.local_state:
            return self.local_state['playerState']['subtitle']
        else:
            return None

    @property
    def supported_features(self):
        features = BASE_FEATURES

        if self.local_state and 'playerState' in self.local_state:
            features |= SUPPORT_PLAY | SUPPORT_PAUSE | SUPPORT_SEEK

            if self.local_state['playerState']['hasPrev']:
                features |= SUPPORT_PREVIOUS_TRACK
            if self.local_state['playerState']['hasNext']:
                features |= SUPPORT_NEXT_TRACK

        elif self.cloud_state:
            features |= (SUPPORT_PLAY | SUPPORT_PAUSE |
                         SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK)

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
        if attrs and self.local_state:
            attrs['alice_state'] = self.local_state['aliceState']
        return attrs

    async def async_select_sound_mode(self, sound_mode):
        self._sound_mode = sound_mode
        self.async_schedule_update_ha_state()

    async def async_mute_volume(self, mute):
        # уводим в mute, только если есть громкость
        if mute and self.volume_level > 0:
            volume = 0
            self.prev_volume = self.volume_level
        # выводим из mute, только если сами в него ушли
        elif not mute and self.prev_volume:
            volume = self.prev_volume
            self.prev_volume = None
        else:
            return

        await self.async_set_volume_level(volume)

    async def async_set_volume_level(self, volume):
        # громкость пригодится для Яндекс.Станции Мини в локальном режиме
        self.cloud_volume = volume

        if self.local_state:
            # у станции округление громкости до десятых
            await self.send_to_station({
                'command': 'setVolume',
                'volume': round(volume, 1)
            })

        else:
            command = f"громкость на {round(10 * volume)}"
            await self.quasar.send(self.device, command)
            self.async_schedule_update_ha_state()

    async def async_media_seek(self, position):
        if self.local_state:
            await self.send_to_station({
                'command': 'rewind', 'position': position})

    async def async_media_play(self):
        if self.local_state:
            await self.send_to_station({'command': 'play'})

        else:
            await self.quasar.send(self.device, "продолжить")
            self.cloud_state = STATE_PLAYING
            self.async_schedule_update_ha_state()

    async def async_media_pause(self):
        if self.local_state:
            await self.send_to_station({'command': 'stop'})

        else:
            await self.quasar.send(self.device, "пауза")
            self.cloud_state = STATE_PAUSED
            self.async_schedule_update_ha_state()

    async def async_media_stop(self):
        await self.async_media_pause()

    async def async_media_previous_track(self):
        if self.local_state:
            await self.send_to_station({'command': 'prev'})
        else:
            await self.quasar.send(self.device, "прошлый трек")

    async def async_media_next_track(self):
        if self.local_state:
            await self.send_to_station({'command': 'next'})
        else:
            await self.quasar.send(self.device, "следующий трек")

    async def async_turn_on(self):
        if self.local_state:
            await self.send_to_station(utils.update_form(
                'personal_assistant.scenarios.player_continue'))
        else:
            await self.async_media_play()

    async def async_turn_off(self):
        if self.local_state:
            await self.send_to_station(utils.update_form(
                'personal_assistant.scenarios.quasar.go_home'))
        else:
            await self.async_media_pause()

    async def update(self, data: dict = None):
        """Обновления только в локальном режиме."""
        data['state'].pop('timeSinceLastVoiceActivity', None)

        # _LOGGER.debug(data['state']['aliceState'])

        # skip same state
        if self.local_state == data['state']:
            return

        self.local_state = data['state']

        # возвращаем из состояния mute, если нужно
        if self.prev_volume and self.local_state['volume']:
            self.prev_volume = None

        # noinspection PyBroadException
        try:
            data = data['extra']['appState'].encode('ascii')
            data = base64.b64decode(data)
            m = RE_EXTRA.search(data)
            self.local_extra = json.loads(m[0]) if m else None
        except Exception:
            self.local_extra = None

        self.local_updated_at = dt.utcnow()

        # _LOGGER.debug(f"Update state {self._config['id']}")

        self.async_schedule_update_ha_state()

    async def response(self, card: dict, request_id: str):
        _LOGGER.debug(f"{self.name} | {card['text']} | {request_id}")

        if request_id in self.requests:
            if card['type'] == 'simple_text':
                text = card['text']

            elif card['type'] == 'text_with_button':
                text = card['text']

                for button in card['buttons']:
                    assert button['type'] == 'action'
                    for directive in button['directives']:
                        if directive['name'] == 'open_uri':
                            title = button['title']
                            uri = directive['payload']['uri']
                            text += f"\n[{title}]({uri})"

            else:
                _LOGGER.error(f"Неизвестный тип ответа: {card['type']}")
                return

            self.hass.bus.async_fire(f"{DOMAIN}_response", {
                'entity_id': self.entity_id,
                'name': self.name,
                'text': text,
                'request_id': self.requests.pop(request_id)
            })

    async def async_play_media(self, media_type: str, media_id: str, **kwargs):
        if '/api/tts_proxy/' in media_id:
            session = async_get_clientsession(self.hass)
            media_id = await utils.get_tts_message(session, media_id)
            media_type = 'tts'

        if not media_id:
            _LOGGER.warning(f"Получено пустое media_id")
            return

        if media_type == 'tts':
            media_type = 'text' if self.sound_mode == SOUND_MODE1 \
                else 'command'

        if self.local_state:
            if 'https://' in media_id or 'http://' in media_id:
                session = async_get_clientsession(self.hass)
                payload = await utils.get_media_payload(media_id, session)
                if not payload:
                    _LOGGER.warning(f"Unsupported url: {media_id}")
                    return

            elif media_type == 'text':
                # даже в локальном режиме делам TTS через облако, чтоб колонка
                # не продолжала слушать
                if self.quasar.main_token:
                    media_id = utils.fix_cloud_text(media_id)
                    if len(media_id) > 100:
                        raise EXCEPTION_100
                    await self.quasar.send(self.device, media_id, is_tts=True)
                    return

                else:
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

            elif media_type.startswith('question'):
                request_id = str(uuid.uuid4())
                self.requests[request_id] = (media_type.split(':', 1)[1]
                                             if ':' in media_type else None)
                await self.send_to_station(
                    {'command': 'sendText', 'text': media_id}, request_id)
                return

            else:
                _LOGGER.warning(f"Unsupported media: {media_id}")
                return

            await self.send_to_station(payload)

        else:
            if media_type == 'text':
                media_id = utils.fix_cloud_text(media_id)
                await self.quasar.send(self.device, media_id, is_tts=True)

            elif media_type == 'command':
                media_id = utils.fix_cloud_text(media_id)
                await self.quasar.send(self.device, media_id)

            else:
                _LOGGER.warning(f"Unsupported media: {media_type}")
                return


class YandexIntents(MediaPlayerEntity):
    def __init__(self, intents: list):
        self.intents = intents

    @property
    def name(self):
        return "Yandex Intents"

    @property
    def supported_features(self):
        return (SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_VOLUME_SET |
                SUPPORT_VOLUME_STEP)

    async def async_volume_up(self):
        pass

    async def async_volume_down(self):
        pass

    async def async_set_volume_level(self, volume):
        index = int(volume * 100) - 1
        if index < len(self.intents):
            text = self.intents[index]
            _LOGGER.debug(f"Получена команда: {text}")
            self.hass.bus.async_fire('yandex_intent', {'text': text})

    async def async_turn_on(self):
        pass

    async def async_turn_off(self):
        pass


SOURCE_STATION = 'Станция'
SOURCE_HDMI = 'HDMI'


# noinspection PyAbstractClass
class YandexStationHDMI(YandexStation):
    device_config = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.device_config = await self.quasar.get_device_config(self.device)

    @property
    def device_class(self) -> Optional[str]:
        return DEVICE_CLASS_TV

    @property
    def supported_features(self):
        return super().supported_features | SUPPORT_SELECT_SOURCE

    @property
    def source(self):
        return SOURCE_HDMI if self.device_config.get('hdmiAudio') \
            else SOURCE_STATION

    @property
    def source_list(self):
        return [SOURCE_STATION, SOURCE_HDMI]

    async def async_select_source(self, source):
        if source == SOURCE_STATION:
            self.device_config.pop('hdmiAudio', None)
        else:
            self.device_config['hdmiAudio'] = True

        await self.quasar.set_device_config(self.device, self.device_config)

        self.async_schedule_update_ha_state()
