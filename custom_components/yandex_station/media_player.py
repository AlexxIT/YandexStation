import asyncio
import base64
import json
import logging
import re
import time
import uuid
from typing import Optional

import yaml
from homeassistant.components import shopping_list
from homeassistant.components.media_player import SUPPORT_PAUSE, \
    SUPPORT_VOLUME_SET, SUPPORT_PREVIOUS_TRACK, \
    SUPPORT_NEXT_TRACK, SUPPORT_PLAY, SUPPORT_TURN_OFF, \
    SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_MUTE, SUPPORT_PLAY_MEDIA, \
    SUPPORT_SEEK, SUPPORT_SELECT_SOUND_MODE, SUPPORT_TURN_ON, \
    DEVICE_CLASS_TV, SUPPORT_SELECT_SOURCE
from homeassistant.components.media_player.const import MEDIA_TYPE_TVSHOW, \
    MEDIA_TYPE_CHANNEL
from homeassistant.config_entries import CONN_CLASS_LOCAL_PUSH, \
    CONN_CLASS_LOCAL_POLL, CONN_CLASS_ASSUMED
from homeassistant.const import STATE_PLAYING, STATE_PAUSED, STATE_IDLE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt

from . import DOMAIN, DATA_CONFIG, CONF_INCLUDE, CONF_INTENTS
from .core import utils
from .core.yandex_glagol import YandexGlagol
from .core.yandex_quasar import YandexQuasar

try:  # поддержка старых версий Home Assistant
    from homeassistant.components.media_player import MediaPlayerEntity
except:
    from homeassistant.components.media_player import \
        MediaPlayerDevice as MediaPlayerEntity

_LOGGER = logging.getLogger(__name__)

RE_EXTRA = re.compile(br'{".+?}\n')
RE_MUSIC_ID = re.compile(r'^\d+(:\d+)?$')
RE_SHOPPING = re.compile(r'^\d+\) (.+)\.$', re.MULTILINE)

BASE_FEATURES = (SUPPORT_TURN_OFF | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP |
                 SUPPORT_VOLUME_MUTE | SUPPORT_PLAY_MEDIA |
                 SUPPORT_SELECT_SOUND_MODE | SUPPORT_TURN_ON)

SOUND_MODE1 = "Произнеси текст"
SOUND_MODE2 = "Выполни команду"

EXCEPTION_100 = Exception("Нельзя произнести более 100 симоволов :(")

# Thanks to: https://github.com/iswitch/ha-yandex-icons
CUSTOM = {
    'yandexstation': ['yandex:station', "Яндекс", "Станция"],
    'yandexstation_2': ['yandex:station-max', "Яндекс", "Станция Макс"],
    'yandexmini': ['yandex:station-mini', "Яндекс", "Станция Мини"],
    'yandexmini_2': ['yandex:station-mini-2', "Яндекс", "Станция Мини 2"],
    'yandexmicro': ['yandex:station-lite', "Яндекс", "Станция Лайт"],
    'yandexmodule': ['yandex:module', "Яндекс", "Модуль"],
    'yandexmodule_2': ['yandex:module-2', "Яндекс", "Модуль 2"],
    'lightcomm': ['yandex:dexp-smartbox', "DEXP", "Smartbox"],
    'elari_a98': ['yandex:elari-smartbeat', "Elari", "SmartBeat"],
    'linkplay_a98': ['yandex:irbis-a', "IRBIS", "A"],
    'wk7y': ['yandex:lg-xboom-wk7y', "LG", "XBOOM AI ThinQ WK7Y"],
    'prestigio_smart_mate': ['yandex:prestigio-smartmate', "Prestigio",
                             "Smartmate"],
    'jbl_link_music': ['yandex:jbl-link-music', "JBL", "Link Music"],
    'jbl_link_portable': ['yandex:jbl-link-portable', "JBL", "Link Portable"],
}

DEVICES = ['devices.types.media_device.tv']


async def async_setup_entry(hass, entry, async_add_entities):
    quasar = hass.data[DOMAIN][entry.unique_id]
    speakers = hass.data[DOMAIN][DATA_CONFIG]

    # add Yandex stations
    entities = []
    for speaker in await quasar.load_speakers():
        speaker['entity'] = entity = (
            YandexStationHDMI(quasar, speaker)
            if speaker['quasar_info']['platform'] in
               ('yandexstation', 'yandexstation_2')
            else YandexStation(quasar, speaker)
        )
        entities.append(entity)
    async_add_entities(entities, True)

    # add TVs
    if CONF_INCLUDE not in hass.data[DOMAIN][DATA_CONFIG]:
        return

    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    entities = [
        YandexTV(quasar, device)
        for device in quasar.devices
        if device['name'] in include and device['type'] in DEVICES
    ]
    async_add_entities(entities, True)


# noinspection PyUnusedLocal
def setup_platform(hass, config, add_entities, discovery_info=None):
    # only intents setup via setup platform
    intents = discovery_info[CONF_INTENTS]
    add_entities([YandexIntents(intents)])


# noinspection PyAbstractClass
class YandexStation(MediaPlayerEntity):
    # имя колонки, есть в обоих режимах
    _name: Optional[str] = None
    # режим звука, есть в обоих режимах
    _sound_mode = SOUND_MODE1
    # кастомная иконка
    _icon = None

    local_state = None
    # экстра есть только в локальном режиме
    local_extra: Optional[dict] = None
    # время обновления состояния (для ползунка), есть только в локальном режиме
    local_updated_at = None
    # прошлая громкость для правильного mute, есть в обоих режимах
    prev_volume = None
    # для управления громкостью Алисы
    alice_volume = None

    # облачное состояние, должно быть null, когда появляется локальное
    cloud_state = STATE_IDLE
    # облачный звук
    cloud_volume = .5

    glagol = None

    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device
        self.requests = {}

    def debug(self, text: str):
        _LOGGER.debug(f"{self.name} | {text}")

    async def async_added_to_hass(self):
        # TODO: проверить смену имени!!!
        self._name = self.device['name']

        if (await utils.has_custom_icons(self.hass) and
                self.device_platform in CUSTOM):
            self._icon = CUSTOM[self.device_platform][0]
            _LOGGER.debug(f"Установка кастомной иконки: {self._icon}")

        if 'host' in self.device:
            await self.init_local_mode()

    async def async_will_remove_from_hass(self):
        if self.glagol:
            await self.glagol.stop()

    async def init_local_mode(self):
        if not self.glagol:
            self.glagol = YandexGlagol(self.quasar.session, self.device)
            self.glagol.update_handler = self.internal_update

        await self.glagol.start_or_restart()

    @property
    def device_platform(self):
        return self.device['quasar_info']['platform']

    @property
    def should_poll(self):
        return self.local_state is None

    @property
    def unique_id(self):
        return self.device['quasar_info']['device_id']

    @property
    def name(self):
        return self._name

    @property
    def device_info(self):
        # https://developers.home-assistant.io/docs/device_registry_index/
        return {
            'identifiers': {(DOMAIN, self.unique_id)},
            'manufacturer': CUSTOM[self.device_platform][1],
            'model': CUSTOM[self.device_platform][2],
            'name': self.device['name'],
        } if self.device_platform in CUSTOM else {
            'identifiers': {(DOMAIN, self.unique_id)},
            'name': self.device['name'],
        }

    @property
    def available(self):
        return bool(self.local_state) or self.device.get('online')

    @property
    def player_state(self):
        return self.local_state and 'playerState' in self.local_state

    @property
    def state(self):
        if self.local_state:
            if self.player_state:
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
        if (self.local_state and isinstance(self.local_state['volume'], float)
                and 0 <= self.local_state['volume'] <= 1):
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
        """Supports: channel (radio)"""
        if not self.player_state:
            return None

        state = self.local_state['playerState']

        if state.get('liveStreamText') == "Прямой эфир":
            return MEDIA_TYPE_CHANNEL  # radio

        # music, podcast also shows as music
        if state['extra']:
            return state['extra']['stateType']  # music

        try:
            type_ = self.local_extra['item']['type']
            if type_ == 'tv_show_episode':
                return MEDIA_TYPE_TVSHOW
            return type_  # movie (kinopoisk) or video (youtube)
        except:
            return None

    @property
    def media_duration(self):
        if self.player_state:
            return self.local_state['playerState']['duration']
        else:
            return None

    @property
    def media_position(self):
        if self.player_state:
            return self.local_state['playerState']['progress']
        else:
            return None

    @property
    def media_position_updated_at(self):
        # TODO: check this
        return self.local_updated_at

    @property
    def media_image_url(self):
        if not self.player_state:
            return None

        try:
            if self.media_content_type == 'music':
                url = self.local_state['playerState']['extra']['coverURI']
                return 'https://' + url.replace('%%', '400x400')
            elif self.media_content_type:
                return self.local_extra['item']['thumbnail_url_16x9']
        except:
            return None

    @property
    def media_image_remotely_accessible(self) -> bool:
        return True

    @property
    def media_title(self):
        if self.player_state:
            return self.local_state['playerState']['title']
        else:
            return None

    @property
    def media_artist(self):
        if self.player_state:
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
    def device_state_attributes(self):
        if self.local_state:
            conn_class = CONN_CLASS_LOCAL_PUSH \
                if self.local_state['local_push'] \
                else CONN_CLASS_LOCAL_POLL
            return {
                'alice_state': self.local_state['aliceState'],
                'connection_class': conn_class
            }
        else:
            return {'connection_class': CONN_CLASS_ASSUMED}

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
            await self.glagol.send({
                'command': 'setVolume',
                'volume': round(volume, 1)
            })

        else:
            command = f"громкость на {round(10 * volume)}"
            await self.quasar.send(self.device, command)
            self.async_schedule_update_ha_state()

    async def async_media_seek(self, position):
        if self.local_state:
            await self.glagol.send({
                'command': 'rewind', 'position': position})

    async def async_media_play(self):
        if self.local_state:
            await self.glagol.send({'command': 'play'})

        else:
            await self.quasar.send(self.device, "продолжить")
            self.cloud_state = STATE_PLAYING
            self.async_schedule_update_ha_state()

    async def async_media_pause(self):
        if self.local_state:
            await self.glagol.send({'command': 'stop'})

        else:
            await self.quasar.send(self.device, "пауза")
            self.cloud_state = STATE_PAUSED
            self.async_schedule_update_ha_state()

    async def async_media_stop(self):
        await self.async_media_pause()

    async def async_media_previous_track(self):
        if self.local_state:
            await self.glagol.send({'command': 'prev'})
        else:
            await self.quasar.send(self.device, "прошлый трек")

    async def async_media_next_track(self):
        if self.local_state:
            await self.glagol.send({'command': 'next'})
        else:
            await self.quasar.send(self.device, "следующий трек")

    async def async_turn_on(self):
        if self.local_state:
            await self.glagol.send(utils.update_form(
                'personal_assistant.scenarios.player_continue'))
        else:
            await self.async_media_play()

    async def async_turn_off(self):
        if self.local_state:
            await self.glagol.send(utils.update_form(
                'personal_assistant.scenarios.quasar.go_home'))
        else:
            await self.async_media_pause()

    async def async_update(self):
        try:
            await self.quasar.update_online_stats()
        except:
            pass

    async def internal_update(self, data: dict = None):
        """Обновления только в локальном режиме."""
        if data is None:
            _LOGGER.debug("Возврат в облачный режим")
            self.local_state = None
            self.async_write_ha_state()
            return

        data['state'].pop('timeSinceLastVoiceActivity', None)

        # _LOGGER.debug(data['state']['aliceState'])
        data['state']['local_push'] = 'requestId' not in data

        # skip same state
        if self.local_state == data['state']:
            return

        self.local_state = data['state']

        # возвращаем из состояния mute, если нужно
        if self.prev_volume and self.local_state['volume']:
            self.prev_volume = None

        if self.alice_volume:
            self._process_alice_volume(self.local_state['aliceState'])

        # noinspection PyBroadException
        try:
            data = data['extra']['appState'].encode('ascii')
            data = base64.b64decode(data)
            m = RE_EXTRA.search(data)
            self.local_extra = json.loads(m[0]) if m else None
        except Exception:
            self.local_extra = None

        self.local_updated_at = dt.utcnow()

        if self.hass:
            self.async_write_ha_state()

    async def response(self, card: dict, request_id: str):
        _LOGGER.debug(f"{self.name} | {card['text']} | {request_id}")

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
            'request_id': request_id
        })

    async def _set_brightness(self, value: str):
        if self.device_platform not in ('yandexstation_2', 'yandexmini_2'):
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

        if 0 <= value <= 1:
            device_config['led']['brightness']['auto'] = False
            device_config['led']['brightness']['value'] = value
        else:
            device_config['led']['brightness']['auto'] = True

        await self.quasar.set_device_config(self.device, device_config)

    async def _set_beta(self, value: str):
        device_config = await self.quasar.get_device_config(self.device)

        if value == 'True':
            value = True
        elif value == 'False':
            value = False
        else:
            value = None

        if value is not None:
            device_config['beta'] = value
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

        card = await self.glagol.send({'command': 'sendText',
                                       'text': "Что в списке покупок"})
        alice_list = RE_SHOPPING.findall(card['text'])
        _LOGGER.debug(f"Список покупок: {alice_list}")

        remove_from = [
            alice_list.index(item['name'])
            for item in data.items
            if item['complete'] and item['name'] in alice_list
        ]
        if remove_from:
            # не может удалить больше 6 штук за раз
            remove_from = sorted(remove_from, reverse=True)
            for i in range(0, len(remove_from), 6):
                items = [str(p + 1) for p in remove_from[i:i + 6]]
                text = "Удали из списка покупок: " + ', '.join(items)
                await self.glagol.send({'command': 'sendText', 'text': text})

        add_to = [
            item['name'] for item in data.items
            if not item['complete'] and item['name'] not in alice_list and
               not item['id'].startswith('alice')
        ]
        for name in add_to:
            # плохо работает, если добавлять всё сразу через запятую
            text = "Добавь в список покупок " + name
            await self.glagol.send({'command': 'sendText', 'text': text})

        if add_to or remove_from:
            card = await self.glagol.send({'command': 'sendText',
                                           'text': "Что в списке покупок"})
            alice_list = RE_SHOPPING.findall(card['text'])
            _LOGGER.debug(f"Новый список покупок: {alice_list}")

        data.items = [
            {'name': name, 'id': 'alice' + uuid.uuid4().hex, 'complete': False}
            for name in alice_list
        ]
        await self.hass.async_add_executor_job(data.save)

    def _check_set_alice_volume(self, extra: dict, dialog: bool):
        alice_volume = extra.get('volume_level')
        # если громкости голоса нет, или уже есть активная громкость, или
        # громкость голоса равна текущей громкости колонки - ничего не делаем
        if (not alice_volume or self.alice_volume or
                alice_volume == self.volume_level):
            return

        self.alice_volume = {
            'volume_level': alice_volume,
            'wait_state': 'BUSY',
            'wait_ts': time.time() + 30
        }

        # для локального TTS не жём статус BUSY
        if dialog:
            self._process_alice_volume('BUSY')

    def _process_alice_volume(self, alice_state: str):
        volume = None

        # если что-то пошло не так, через 30 секунд возвращаем громкость
        if time.time() > self.alice_volume['wait_ts']:
            volume = self.alice_volume['prev_volume']
            self.alice_volume = None

        elif self.alice_volume['wait_state'] == alice_state:
            if alice_state == 'BUSY':
                volume = self.alice_volume['volume_level']
                self.alice_volume['prev_volume'] = self.volume_level
                self.alice_volume['wait_state'] = 'SPEAKING'

            elif alice_state == 'SPEAKING':
                self.alice_volume['wait_state'] = 'IDLE'

            elif alice_state == 'IDLE':
                volume = self.alice_volume['prev_volume']
                self.alice_volume = None

        if volume:
            coro = self.async_set_volume_level(volume)
            asyncio.create_task(coro)

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
        elif media_type == 'brightness':
            await self._set_brightness(media_id)
            return
        elif media_type == 'beta':
            await self._set_beta(media_id)
            return
        elif media_type == 'settings':
            await self._set_settings(media_id)
            return

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
                if self.quasar.session.x_token:
                    media_id = utils.fix_cloud_text(media_id)
                    if len(media_id) > 100:
                        raise EXCEPTION_100
                    if 'extra' in kwargs:
                        self._check_set_alice_volume(kwargs['extra'], False)
                    await self.quasar.send(self.device, media_id, is_tts=True)
                    return

                else:
                    payload = {'command': 'sendText',
                               'text': f"Повтори за мной '{media_id}'"}

            elif media_type == 'command':
                payload = {'command': 'sendText', 'text': media_id}

            elif media_type == 'dialog':
                if 'extra' in kwargs:
                    self._check_set_alice_volume(kwargs['extra'], True)
                payload = utils.update_form(
                    'personal_assistant.scenarios.repeat_after_me',
                    request=media_id)

            elif media_type == 'json':
                payload = json.loads(media_id)

            elif RE_MUSIC_ID.match(media_id):
                payload = {'command': 'playMusic', 'id': media_id,
                           'type': media_type}

            elif media_type == 'shopping_list':
                await self._shopping_list()
                return

            elif media_type.startswith('question'):
                request_id = (media_type.split(':', 1)[1]
                              if ':' in media_type else None)
                card = await self.glagol.send({'command': 'sendText',
                                               'text': media_id})
                await self.response(card, request_id)
                return

            else:
                _LOGGER.warning(f"Unsupported local media: {media_id}")
                return

            await self.glagol.send(payload)

        else:
            if media_type == 'text':
                media_id = utils.fix_cloud_text(media_id)
                await self.quasar.send(self.device, media_id, is_tts=True)

            elif media_type == 'command':
                media_id = utils.fix_cloud_text(media_id)
                await self.quasar.send(self.device, media_id)

            elif media_type == 'brightness':
                await self._set_brightness(media_id)
                return

            else:
                _LOGGER.warning(f"Unsupported cloud media: {media_type}")
                return


# noinspection PyAbstractClass
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
        features = super().supported_features
        if self.device_config:
            features |= SUPPORT_SELECT_SOURCE
        return features

    @property
    def source(self):
        if self.device_config:
            hdmi = self.device_config.get('hdmiAudio')
            return SOURCE_HDMI if hdmi else SOURCE_STATION
        return None

    @property
    def source_list(self):
        return [SOURCE_STATION, SOURCE_HDMI]

    async def async_select_source(self, source):
        # update config to actual state
        device_config = await self.quasar.get_device_config(self.device)
        if not device_config:
            _LOGGER.warning("Не получается получить настройки станции")
            return

        if source == SOURCE_STATION:
            device_config.pop('hdmiAudio', None)
        else:
            device_config['hdmiAudio'] = True

        await self.quasar.set_device_config(self.device, device_config)

        self.device_config = device_config
        self.async_schedule_update_ha_state()


# noinspection PyAbstractClass
class YandexTV(MediaPlayerEntity):
    _sources = None
    _supported_features = 0

    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device

    @property
    def unique_id(self):
        return self.device['id'].replace('-', '')

    @property
    def name(self):
        return self.device['name']

    @property
    def should_poll(self):
        return False

    @property
    def device_class(self):
        return DEVICE_CLASS_TV

    @property
    def icon(self):
        return 'mdi:television-classic'

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
        await self.quasar.device_action(self.device['id'], on=True)

    async def async_turn_off(self):
        await self.quasar.device_action(self.device['id'], on=False)

    async def async_volume_up(self):
        await self.quasar.device_action(self.device['id'], volume=1)

    async def async_volume_down(self):
        await self.quasar.device_action(self.device['id'], volume=-1)

    async def async_mute_volume(self, mute):
        await self.quasar.device_action(self.device['id'], mute=mute)

    async def async_media_next_track(self):
        await self.quasar.device_action(self.device['id'], channel=1)

    async def async_media_previous_track(self):
        await self.quasar.device_action(self.device['id'], channel=-1)

    async def async_media_pause(self):
        await self.quasar.device_action(self.device['id'], pause=True)

    async def async_select_source(self, source):
        source = self._sources[source]
        await self.quasar.device_action(self.device['id'], input_source=source)

    async def async_added_to_hass(self):
        data = await self.quasar.get_device(self.device['id'])
        for capability in data['capabilities']:
            instance = capability['parameters'].get('instance')
            if capability['type'] == 'devices.capabilities.on_off':
                self._supported_features |= \
                    SUPPORT_TURN_ON | SUPPORT_TURN_OFF
            elif instance == 'volume':
                self._supported_features |= SUPPORT_VOLUME_STEP
            elif instance == 'channel':
                self._supported_features |= \
                    SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK
            elif instance == 'input_source':
                self._sources = {
                    p['name']: p['value']
                    for p in capability['parameters']['modes']
                }
                self._supported_features |= SUPPORT_SELECT_SOURCE
            elif instance == 'mute':
                self._supported_features |= SUPPORT_VOLUME_MUTE
            elif instance == 'pause':
                # without play, pause from the interface does not work
                self._supported_features |= SUPPORT_PAUSE | SUPPORT_PLAY
