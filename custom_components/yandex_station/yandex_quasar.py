import base64
import json
import logging
import os
import pickle
import re
from typing import Optional

from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)

HEADERS = {'User-Agent': 'com.yandex.mobile.auth.sdk/7.15.0.715001762'}

RE_CSRF = re.compile('"csrfToken2":"(.+?)"')

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
    # don't works
    'hsv': 'devices.capabilities.color_setting',
    'rgb': 'devices.capabilities.color_setting',
    'temperature_k': 'devices.capabilities.color_setting',
}

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
    # all devices
    devices = None

    def __init__(self, session: ClientSession):
        self.session = session
        session.request = self._request

    async def _request(self, method: str, url: str, **kwargs):
        """Запрос с учётом CSRF-токена."""
        for _ in range(3):
            if method != 'get':
                if self.csrf_token is None:
                    _LOGGER.debug("Обновление CSRF-токена")
                    r = await self.session.get('https://yandex.ru/quasar/iot')
                    raw = await r.text()
                    m = RE_CSRF.search(raw)
                    assert m, raw
                    self.csrf_token = m[1]

                kwargs['headers'] = {'x-csrf-token': self.csrf_token}

            r = await getattr(self.session, method)(url, **kwargs)

            if r.status == 401:
                # 401 - no cookies
                await self.login(self.main_token['access_token'])
            elif r.status == 403:
                # 403 - no x-csrf-token
                self.csrf_token = None
            elif r.status == 200:
                return r
            else:
                _LOGGER.warning(f"{url} return {r.status} status")

        raise Exception(f"{url} return {r.status} status")

    async def init(self, username: str, password: str, cachefile: str) \
            -> Optional[list]:
        """Основная функция. Возвращает список колонок."""
        try:
            self.load(cachefile)

            if not self.main_token:
                self.main_token = await self.get_main_token(username, password)

            if not await self.check_login():
                await self.login(self.main_token['access_token'])
                self.save(cachefile)

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
            'x_token_client_id': 'c0ebe342af7d48fbbbfcf2d2eedb8f9e',
            'x_token_client_secret': 'ad0a908f0aa341a182a37ecd75bc319e',
            'client_id': 'f8cab64f154b4c8e96f92dac8becfcaa',
            'client_secret': '5dd2389483934f02bd51eaa749add5b2',
            'display_language': 'ru',
            'force_register': 'false',
            'is_phone_number': 'false',
            'login': username,
        }
        r = await self.session.post(
            'https://mobileproxy.passport.yandex.net/2/bundle/mobile/start/',
            data=payload, headers=HEADERS)
        resp = await r.json()
        assert 'track_id' in resp, resp

        payload = {
            'password_source': 'Login',
            'password': password,
            'track_id': resp['track_id']
        }
        r = await self.session.post(
            'https://mobileproxy.passport.yandex.net/1/bundle/mobile/auth/'
            'password/', data=payload, headers=HEADERS)
        resp = await r.json()
        assert 'x_token' in resp, resp

        return {
            'access_token': resp['x_token'],
            'expires_in': resp['x_token_expires_in'],
            'issued_at': resp['x_token_issued_at']
        }

    async def user_info(self, token: str):
        """Информация о пользователе."""
        payload = {'token': token, 'size': 'islands-300'}
        r = await self.session.post(
            'https://registrator.mobile.yandex.net/1/user_info',
            data=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        return resp

    async def check_login(self) -> bool:
        try:
            r = await self.session.get(
                'https://iot.quasar.yandex.ru/m/user/devices')
            resp = await r.json()
            return resp['status'] == 'ok'
        except:
            return False

    async def login(self, x_token: str):
        _LOGGER.debug("Логин в Яндексе через главный токен.")

        # python 3.8 cookie error fix
        self.session.cookie_jar.clear()

        payload = {
            'type': 'x-token',
            'retpath': 'https://www.yandex.ru/androids.txt'
        }
        headers = {'Ya-Consumer-Authorization': f"OAuth {x_token}"}
        r = await self.session.post(
            'https://mobileproxy.passport.yandex.net/1/bundle/auth/x_token/',
            data=payload, headers=headers)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        host = resp['passport_host']
        payload = {'track_id': resp['track_id']}
        r = await self.session.get(f"{host}/auth/session/", params=payload)
        assert r.status == 404, await r.read()

    async def load_speakers(self) -> list:
        _LOGGER.debug("Получение списка устройств.")

        r = await self.session.request(
            'get', 'https://iot.quasar.yandex.ru/m/user/devices')
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        self.devices = [device for room in resp['rooms']
                        for device in room['devices']]

        speakers = resp['speakers'] + [
            device for device in self.devices
            if device['type'].startswith('devices.types.smart_speaker') or
               device['type'].endswith('yandex.module')
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
        r = await self.session.request(
            'get', f"https://iot.quasar.yandex.ru/m/user/devices/"
                   f"{device['id']}/configuration")
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        # device_id and platform
        device.update(resp['quasar_info'])

    async def load_scenarios(self) -> dict:
        """Получает список сценариев, которые мы ранее создали."""
        r = await self.session.request(
            'get', 'https://iot.quasar.yandex.ru/m/user/scenarios')
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        return {
            decode(d['name']): d
            for d in resp['scenarios']
            if d['name'].startswith('ХА ')
        }

    async def add_scenario(self, device_id: str):
        """Добавляет сценарий-пустышку."""
        payload = {
            'name': encode(device_id),
            'icon': 'home',
            'trigger_type': 'scenario.trigger.voice',
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
        r = await self.session.request(
            'post', 'https://iot.quasar.yandex.ru/m/user/scenarios',
            json=payload)
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
            'trigger_type': 'scenario.trigger.voice',
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
        r = await self.session.request(
            'post', 'https://iot.quasar.yandex.ru/m/user/scenarios',
            json=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def send(self, device: dict, text: str, is_tts: bool = False):
        """Запускает сценарий на выполнение команды или TTS.
        """
        device_id = device['id']
        _LOGGER.debug(f"{device['name']} => cloud | {text}")

        action = 'phrase_action' if is_tts else 'text_action'
        payload = {
            'name': encode(device_id),
            'icon': 'home',
            'trigger_type': 'scenario.trigger.voice',
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

        r = await self.session.request(
            'put', f"https://iot.quasar.yandex.ru/m/user/scenarios/{sid}",
            json=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        r = await self.session.request(
            'post',
            f"https://iot.quasar.yandex.ru/m/user/scenarios/{sid}/actions")
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

    async def get_device_config(self, device: dict) -> dict:
        payload = {'device_id': device['device_id'],
                   'platform': device['platform']}
        r = await self.session.request(
            'get', 'https://quasar.yandex.ru/get_device_config',
            params=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        return resp['config']

    async def set_device_config(self, device: dict, device_config: dict):
        _LOGGER.debug(f"Меняем конфиг станции: {device_config}")

        payload = {'device_id': device['device_id'],
                   'platform': device['platform']}
        r = await self.session.request(
            'post', 'https://quasar.yandex.ru/set_device_config',
            params=payload, json=device_config)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def get_device(self, deviceid: str):
        url = f"https://iot.quasar.yandex.ru/m/user/devices/{deviceid}"
        r = await self.session.request('get', url)
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        return resp

    async def device_action(self, deviceid: str, **kwargs):
        _LOGGER.debug(f"Device action: {kwargs}")
        url = f"https://iot.quasar.yandex.ru/m/user/devices/{deviceid}/actions"

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

        r = await self.session.request('post', url, json={'actions': actions})
        resp = await r.json()
        assert resp['status'] == 'ok', resp
