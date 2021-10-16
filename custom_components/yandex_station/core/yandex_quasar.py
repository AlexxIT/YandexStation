import asyncio
import json
import logging
import time

from aiohttp import WSMsgType

from .yandex_session import YandexSession

_LOGGER = logging.getLogger(__name__)

IOT_TYPES = {
    'on': 'devices.capabilities.on_off',
    'temperature': 'devices.capabilities.range',
    'fan_speed': 'devices.capabilities.mode',
    'thermostat': 'devices.capabilities.mode',
    'volume': 'devices.capabilities.range',
    'pause': 'devices.capabilities.toggle',
    'mute': 'devices.capabilities.toggle',
    'channel': 'devices.capabilities.range',
    'input_source': 'devices.capabilities.mode',
    'brightness': 'devices.capabilities.range',
    'color': 'devices.capabilities.color_setting',
    'work_speed': 'devices.capabilities.mode',
    # don't work
    'hsv': 'devices.capabilities.color_setting',
    'rgb': 'devices.capabilities.color_setting',
    'temperature_k': 'devices.capabilities.color_setting',
}

MASK_EN = '0123456789abcdef-'
MASK_RU = 'оеаинтсрвлкмдпуяы'

URL_USER = 'https://iot.quasar.yandex.ru/m/user'


def encode(uid: str) -> str:
    """Кодируем UID в рус. буквы. Яндекс привередливый."""
    return 'ХА ' + ''.join([MASK_RU[MASK_EN.index(s)] for s in uid])


def decode(uid: str) -> str:
    """Раскодируем UID из рус.букв."""
    return ''.join([MASK_EN[MASK_RU.index(s)] for s in uid[3:]])


class YandexQuasar:
    # all devices
    devices = None
    online_update_ts = 0

    def __init__(self, session: YandexSession):
        self.session = session

    @property
    def hass_id(self):
        for device in self.devices:
            if device['name'] == "Yandex Intents":
                return device['id']
        return None

    async def init(self):
        """Основная функция. Возвращает список колонок."""
        _LOGGER.debug("Получение списка устройств.")

        r = await self.session.get(f"{URL_USER}/devices")
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        self.devices = [device for room in resp['rooms']
                        for device in room['devices']]
        self.devices += resp['speakers'] + resp['unconfigured_devices']

    @property
    def speakers(self):
        return [
            device for device in self.devices
            if device['type'].startswith('devices.types.smart_speaker') or
               device['type'].endswith('yandex.module')
        ]

    async def load_speakers(self) -> list:
        speakers = self.speakers

        # Яндекс начали добавлять device_id и platform с полным списком
        # устройств
        # for speaker in speakers:
        #     await self.load_speaker_config(speaker)

        scenarios = await self.load_scenarios()
        for speaker in speakers:
            device_id = speaker['id']

            if device_id not in scenarios:
                await self.add_scenario(device_id)
                scenarios = await self.load_scenarios()

            speaker['scenario_id'] = scenarios[device_id]['id']

        return speakers

    async def load_speaker_config(self, device: dict):
        """Загружаем device_id и platform для колонок. Они не приходят с полным
        списком устройств.
        """
        r = await self.session.get(
            f"{URL_USER}/devices/{device['id']}/configuration")
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        # device_id and platform
        device.update(resp['quasar_info'])

    async def load_scenarios(self) -> dict:
        """Получает список сценариев, которые мы ранее создали."""
        r = await self.session.get(f"{URL_USER}/scenarios")
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        return {
            decode(d['name']): d
            for d in resp['scenarios']
            if d['name'].startswith('ХА ')
        }

    async def add_scenario(self, device_id: str):
        """Добавляет сценарий-пустышку."""
        name = encode(device_id)
        payload = {
            'name': name,
            'icon': 'home',
            'triggers': [{
                'type': 'scenario.trigger.voice',
                'value': name[3:]
            }],
            'requested_speaker_capabilities': [],
            'devices': [{
                'id': device_id,
                'capabilities': [{
                    'type': 'devices.capabilities.quasar.server_action',
                    'state': {
                        'instance': 'phrase_action',
                        'value': 'пустышка'
                    }
                }]
            }]
        }
        r = await self.session.post(f"{URL_USER}/scenarios", json=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def add_intent(self, name: str, text: str, num: int):
        speaker = [{
            'type': 'devices.capabilities.quasar.server_action',
            'state': {
                'instance': 'phrase_action',
                'value': text
            }
        }] if text else [{
            'type': 'devices.capabilities.quasar.server_action',
            'state': {
                'instance': 'text_action',
                'value': "Yandex Intents громкость 100"
            }
        }]

        payload = {
            'name': name,
            'icon': 'home',
            'triggers': [{
                'type': 'scenario.trigger.voice',
                'value': name
            }],
            'requested_speaker_capabilities': speaker,
            'devices': [{
                'id': self.hass_id,
                'capabilities': [{
                    'type': 'devices.capabilities.range',
                    'state': {
                        'instance': 'volume',
                        'relative': False,
                        'value': num
                    }
                }]
            }]
        }
        r = await self.session.post(f"{URL_USER}/scenarios", json=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def send(self, device: dict, text: str, is_tts: bool = False):
        """Запускает сценарий на выполнение команды или TTS.
        """
        device_id = device['id']
        _LOGGER.debug(f"{device['name']} => cloud | {text}")

        action = 'phrase_action' if is_tts else 'text_action'
        name = encode(device_id)
        payload = {
            'name': name,
            'icon': 'home',
            'triggers': [{
                'type': 'scenario.trigger.voice',
                'value': name[3:]
            }],
            'requested_speaker_capabilities': [],
            'devices': [{
                'id': device_id,
                'capabilities': [{
                    'type': 'devices.capabilities.quasar.server_action',
                    'state': {
                        'instance': action,
                        'value': text
                    }
                }]
            }]
        }

        sid = device['scenario_id']

        r = await self.session.put(f"{URL_USER}/scenarios/{sid}", json=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        r = await self.session.post(f"{URL_USER}/scenarios/{sid}/actions")
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def load_local_speakers(self):
        """Загружает список локальных колонок. Не используется."""
        try:
            r = await self.session.get(
                'https://quasar.yandex.net/glagol/device_list')
            resp = await r.json()
            return [{
                'device_id': d['id'],
                'name': d['name'],
                'platform': d['platform']
            } for d in resp['devices']]

        except:
            _LOGGER.exception("Load local speakers")
            return None

    async def get_device_config(self, device: dict) -> dict:
        payload = {'device_id': device['quasar_info']['device_id'],
                   'platform': device['quasar_info']['platform']}
        r = await self.session.get(
            'https://quasar.yandex.ru/get_device_config', params=payload
        )
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        return resp['config']

    async def set_device_config(self, device: dict, device_config: dict):
        _LOGGER.debug(f"Меняем конфиг станции: {device_config}")

        payload = {'device_id': device['quasar_info']['device_id'],
                   'platform': device['quasar_info']['platform']}
        r = await self.session.post(
            'https://quasar.yandex.ru/set_device_config', params=payload,
            json=device_config
        )
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def get_device(self, deviceid: str):
        r = await self.session.get(f"{URL_USER}/devices/{deviceid}")
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        return resp

    async def device_action(self, deviceid: str, **kwargs):
        _LOGGER.debug(f"Device action: {kwargs}")

        actions = []
        for k, v in kwargs.items():
            type_ = (
                'devices.capabilities.custom.button'
                if k.isdecimal() else IOT_TYPES[k]
            )
            state = (
                {'instance': k, 'value': v, 'relative': True}
                if k in ('volume', 'channel')
                else {'instance': k, 'value': v}
            )
            actions.append({'type': type_, 'state': state})

        r = await self.session.post(
            f"{URL_USER}/devices/{deviceid}/actions", json={'actions': actions}
        )
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def update_online_stats(self):
        if time.time() < self.online_update_ts:
            return

        _LOGGER.debug(f"Update speakers online status")

        self.online_update_ts = time.time() + 30

        r = await self.session.get(
            'https://quasar.yandex.ru/devices_online_stats')
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        for speaker in resp['items']:
            device = next(
                p for p in self.devices
                if 'quasar_info' in p and
                p['quasar_info']['device_id'] == speaker['id']
            )
            device['online'] = speaker['online']

    async def _updates_connection(self, handler):
        r = await self.session.get(
            'https://iot.quasar.yandex.ru/m/v3/user/devices'
        )
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        ws = await self.session.ws_connect(resp['updates_url'], heartbeat=60)
        _LOGGER.debug("Start quasar updates connection")
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                break
            resp = msg.json()
            if not resp.get('message'):
                continue
            try:
                resp = json.loads(resp['message'])
                for upd in resp['updated_devices']:
                    if not upd.get('capabilities'):
                        continue
                    for cap in upd['capabilities']:
                        state = cap.get('state')
                        if not state:
                            continue
                        if cap['type'] == \
                                'devices.capabilities.quasar.server_action':
                            for speaker in self.speakers:
                                if speaker['id'] == upd['id']:
                                    entity = speaker.get('entity')
                                    if not entity:
                                        break
                                    state['entity_id'] = entity.entity_id
                                    state['name'] = entity.name
                                    await handler(state)
                                    break
            except:
                _LOGGER.debug(f"Parse quasar update error: {msg.data}")

    async def _updates_loop(self, handler):
        while True:
            try:
                await self._updates_connection(handler)
            except Exception as e:
                _LOGGER.debug(f"Quasar update error: {e}")
            await asyncio.sleep(30)

    def handle_updates(self, handler):
        asyncio.create_task(self._updates_loop(handler))

    async def set_user_settings(self, response_sound: bool):
        # https://iot.quasar.yandex.ru/m/user/settings
        value = 'sound' if response_sound else 'nlg'
        r = await self.session.post(URL_USER + '/settings', json={
            'iot': {'response_reaction_type': value}
        })
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def set_account_config(self, key: str, value):
        kv = ACCOUNT_CONFIG.get(key)
        assert kv and value in kv['values'], f"{key}={value}"

        if kv['key'] == 'user/settings':
            return await self.set_user_settings(kv['values'][value])

        r = await self.session.get(
            'https://quasar.yandex.ru/get_account_config'
        )
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        payload = resp['config']
        payload[kv['key']] = kv['values'][value]

        r = await self.session.post(
            'https://quasar.yandex.ru/set_account_config', json=payload
        )
        resp = await r.json()
        assert resp['status'] == 'ok', resp


BOOL_CONFIG = {'да': True, 'нет': False}
ACCOUNT_CONFIG = {
    'без лишних слов': {
        'key': 'user/settings',
        'values': BOOL_CONFIG
    },
    'звук активации': {
        'key': 'jingle',
        'values': BOOL_CONFIG
    },
    'одним устройством': {
        'key': 'smartActivation',
        'values': BOOL_CONFIG
    },
    'понимать детей': {
        'key': 'useBiometryChildScoring',
        'values': BOOL_CONFIG
    },
    'рассказывать о навыках': {
        'key': 'aliceProactivity',
        'values': BOOL_CONFIG
    },
    'взрослый голос': {
        'key': 'contentAccess',
        'values': {
            'умеренный': 'medium',
            'семейный': 'children',
            'безопасный': 'safe',
            'без ограничений': 'without',
        }
    },
    'детский голос': {
        'key': 'childContentAccess',
        'values': {
            'безопасный': 'safe',
            'семейный': 'children',
        }
    },
    'имя': {
        'key': 'spotter',
        'values': {
            'алиса': 'alisa',
            'яндекс': 'yandex',
        }
    },
}
