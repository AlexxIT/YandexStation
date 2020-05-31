import base64
import json
import logging
import os
import pickle
import re
from typing import Optional

from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)

HEADERS = {'User-Agent': 'okhttp/3.5.0'}

RE_CSRF = re.compile('"csrfToken2":"(.+?)"')

MASK_EN = '0123456789abcdef-'
MASK_RU = 'оеаинтсрвлкмдпуяы'


def encode(uid: str) -> str:
    """Кодируем UID в рус. буквы. Яндекс привередливый."""
    return 'ХА ' + ''.join([MASK_RU[MASK_EN.index(s)] for s in uid])


def decode(uid: str) -> str:
    """Раскодируем UID из рус.букв."""
    return ''.join([MASK_EN[MASK_RU.index(s)] for s in uid[3:]])


class YandexQuasar:
    main_token = None
    local_token = None
    csrf_token = None
    cookies = None
    hass_id = None

    def __init__(self, session: ClientSession):
        self.session = session

    async def init(self, username: str, password: str, cachefile: str) \
            -> Optional[list]:
        """Основная функция. Возвращает список колонок."""
        try:
            self.load(cachefile)

            if not self.main_token:
                self.main_token = await self.get_main_token(username, password)
                await self.login(self.main_token['access_token'])
                self.save(cachefile)

            self.csrf_token = await self.get_csrf_token()

            speakers = await self.load_speakers()
            scenarios = await self.load_scenarios()
            for speaker in speakers:
                device_id = speaker['id']

                if device_id not in scenarios:
                    await self.add_scenario(device_id)
                    scenarios = await self.load_scenarios()

                speaker['scenario_id'] = scenarios[device_id]['id']

            return speakers

        except:
            _LOGGER.exception("Init")
            return None

    async def init_local(self, cachefile: str):
        """Получает локальный токен, если его ещё нет."""
        if self.local_token:
            return

        try:
            x_token = self.main_token['access_token']
            self.local_token = await self.get_local_token(x_token)
            self.save(cachefile)

        except:
            _LOGGER.exception("Init local")

    def load(self, filename: str):
        """Загружаем токены и куки из файла."""
        if not os.path.isfile(filename):
            return

        with open(filename, 'rt') as f:
            raw = json.load(f)

        self.main_token = raw['main_token']
        self.local_token = raw['music_token']
        raw = base64.b64decode(raw['cookie'])
        self.session.cookie_jar._cookies = pickle.loads(raw)

    def save(self, filename: str):
        """Сохраняет токены и куки в файл."""
        # noinspection PyProtectedMember, PyUnresolvedReferences
        raw = pickle.dumps(self.session.cookie_jar._cookies,
                           pickle.HIGHEST_PROTOCOL)
        data = {
            'main_token': self.main_token,
            'music_token': self.local_token,
            'cookie': base64.b64encode(raw).decode()
        }
        with open(filename, 'wt') as f:
            json.dump(data, f)

    async def get_main_token(self, username: str, password: str):
        _LOGGER.debug("Получение главного токена Яндекса.")

        payload = {
            # Yandex Mobile
            'client_secret': 'ad0a908f0aa341a182a37ecd75bc319e',
            'client_id': 'c0ebe342af7d48fbbbfcf2d2eedb8f9e',
            'grant_type': 'password',
            'username': username,
            'password': password
        }
        r = await self.session.post('https://oauth.mobile.yandex.net/1/token',
                                    data=payload, headers=HEADERS)
        resp = await r.json()
        assert 'access_token' in resp, resp
        return resp

    async def user_info(self, token: str):
        """Информация о пользователе."""
        payload = {'token': token, 'size': 'islands-300'}
        r = await self.session.post(
            'https://registrator.mobile.yandex.net/1/user_info',
            data=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        return resp

    async def login(self, x_token: str):
        _LOGGER.debug("Логин в Яндексе через главный токен.")

        payload = {
            'type': 'x-token',
            'retpath': 'https://www.yandex.ru/androids.txt'
        }
        headers = {'Ya-Consumer-Authorization': f"OAuth {x_token}"}
        r = await self.session.post(
            'https://registrator.mobile.yandex.net/1/bundle/auth/x_token/',
            data=payload, headers=headers)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        host = resp['passport_host']
        payload = {'track_id': resp['track_id']}
        r = await self.session.get(f"{host}/auth/session/", params=payload)
        assert r.status == 404, await r.read()

    async def load_speakers(self) -> list:
        _LOGGER.debug("Получение списка устройств.")

        r = await self.session.get(
            'https://iot.quasar.yandex.ru/m/user/devices')
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        speakers = resp['speakers'] + [
            device for room in resp['rooms']
            for device in room['devices']
            if device['type'].startswith('devices.types.smart_speaker')
        ]

        for device in resp['unconfigured_devices']:
            if device['name'] == "Yandex Intents":
                self.hass_id = device['id']
                break

        for speaker in speakers:
            await self.load_speaker_config(speaker)

        return speakers

    async def load_speaker_config(self, device: dict):
        """Загружаем device_id и platform для колонок. Они не приходят с полным
        списком устройств.
        """
        r = await self.session.get(f"https://iot.quasar.yandex.ru/m/user/"
                                   f"devices/{device['id']}/configuration")
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        # device_id and platform
        device.update(resp['quasar_info'])

    async def load_scenarios(self) -> dict:
        """Получает список сценариев, которые мы ранее создали."""
        r = await self.session.get(
            'https://iot.quasar.yandex.ru/m/user/scenarios')
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        return {
            decode(d['name']): d
            for d in resp['scenarios']
            if d['name'].startswith('ХА ')
        }

    async def get_csrf_token(self):
        """Получает кроссайтовый токен."""
        r = await self.session.get('https://yandex.ru/quasar/iot')
        raw = await r.text()
        m = RE_CSRF.search(raw)
        assert m, raw
        return m[1]

    async def add_scenario(self, device_id: str):
        """Добавляет сценарий-пустышку."""
        payload = {
            'name': encode(device_id),
            'icon': 'home',
            'trigger_type': 'scenario.trigger.voice',
            'devices': [],
            'external_actions': [{
                'type': 'scenario.external_action.phrase', 'parameters': {
                    'current_device': False,
                    'device_id': device_id,
                    'phrase': '-'
                }
            }]
        }
        headers = {'x-csrf-token': self.csrf_token}
        r = await self.session.post(
            'https://iot.quasar.yandex.ru/m/user/scenarios',
            json=payload, headers=headers)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def add_intent(self, name: str, text: str, num: int):
        payload = {
            'name': name,
            'icon': 'home',
            'trigger_type': 'scenario.trigger.voice',
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
            }],
            'external_actions': [{
                "type": "scenario.external_action.phrase",
                "parameters": {
                    "current_device": True,
                    "phrase": text
                }
            }]
        }
        headers = {'x-csrf-token': self.csrf_token}
        r = await self.session.post(
            'https://iot.quasar.yandex.ru/m/user/scenarios',
            json=payload, headers=headers)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def send(self, device: dict, text: str, is_tts: bool = False):
        """Запускает сценарий на выполнение команды или TTS.
        """
        device_id = device['id']
        _LOGGER.debug(f"{device['name']} => cloud | {text}")

        action = 'phrase' if is_tts else 'text'
        payload = {
            'name': encode(device_id),
            'icon': 'home',
            'trigger_type': 'scenario.trigger.voice',
            'devices': [],
            'external_actions': [{
                'type': f"scenario.external_action.{action}", 'parameters': {
                    'current_device': False,
                    'device_id': device_id,
                    action: text
                }
            }]
        }

        sid = device['scenario_id']
        headers = {'x-csrf-token': self.csrf_token}

        r = await self.session.put(
            f"https://iot.quasar.yandex.ru/m/user/scenarios/{sid}",
            json=payload, headers=headers)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/user/scenarios/{sid}/actions",
            json=payload, headers=headers)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def get_local_token(self, x_token: str):
        _LOGGER.debug("Получение токена для локального протокола.")

        payload = {
            # Thanks to https://github.com/MarshalX/yandex-music-api/
            'client_secret': '53bc75238f0c4d08a118e51fe9203300',
            'client_id': '23cabbbdc6cd418abb4b39c32c41195d',
            'grant_type': 'x-token',
            'access_token': x_token
        }
        r = await self.session.post('https://oauth.mobile.yandex.net/1/token',
                                    data=payload)
        resp = await r.json()
        assert 'access_token' in resp, resp
        return resp

    async def load_local_speakers(self, token: str):
        """Загружает список локальных колонок."""
        self.local_token = {'access_token': token}

        try:
            r = await self.session.get(
                'https://quasar.yandex.net/glagol/device_list',
                headers={'Authorization': f"Oauth {token}"})
            resp = await r.json()
            return [{
                'device_id': d['id'],
                'name': d['name'],
                'platform': d['platform']
            } for d in resp['devices']]

        except:
            _LOGGER.exception("Load local speakers")
            return None
