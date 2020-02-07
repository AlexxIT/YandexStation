import json
import logging
import os
import pickle
import re
from functools import lru_cache
from ssl import SSLContext
from typing import Optional

import requests
import websockets
from websockets import ConnectionClosed

_LOGGER = logging.getLogger(__name__)

# Thanks to https://github.com/MarshalX/yandex-music-api/
CLIENT_ID = '23cabbbdc6cd418abb4b39c32c41195d'
CLIENT_SECRET = '53bc75238f0c4d08a118e51fe9203300'


def load_token(filename: str) -> Optional[str]:
    if os.path.isfile(filename):
        with open(filename, 'rt', encoding='utf-8') as f:
            return f.read()
    return None


def save_token(filename: str, token: str):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(token)


def get_yandex_token(username: str, password: str) -> str:
    r = requests.post('https://oauth.yandex.ru/token', data={
        'grant_type': 'password',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'username': username,
        'password': password
    }, headers={
        'User-Agent': 'Yandex-Music-API',
        'X-Yandex-Music-Client': 'WindowsPhone/3.20',
    })

    _LOGGER.debug(r.text)
    return r.json()['access_token']


@lru_cache()
def get_devices(yandex_token: str) -> dict:
    r = requests.get('https://quasar.yandex.net/glagol/device_list',
                     headers={'Authorization': f"Oauth {yandex_token}"})
    _LOGGER.debug(r.text)
    return r.json()['devices']


def get_device_token(yandex_token: str, device_id: str,
                     device_platform: str) -> str:
    _LOGGER.debug(f"Refresh device token {device_id}")
    r = requests.get('https://quasar.yandex.net/glagol/token', params={
        'device_id': device_id,
        'platform': device_platform
    }, headers={'Authorization': f"Oauth {yandex_token}"})
    _LOGGER.debug(r.text)
    return r.json()['token']


async def send_to_station(device: dict, message: dict = None):
    if 'device_token' not in device:
        device['device_token'] = get_device_token(
            device['yandex_token'], device['id'], device['platform'])

    device_token = device['device_token']

    uri = f"wss://{device['host']}:{device['port']}"
    try:
        async with websockets.connect(uri, ssl=SSLContext()) as ws:
            await ws.send(json.dumps({
                'conversationToken': device_token,
                'payload': message
            }))
            res = json.loads(await ws.recv())
            _LOGGER.debug(res)
            return res

    except ConnectionClosed as e:
        if e.code == 4000:
            device.pop('device_token')
            return await send_to_station(device, message)

    except Exception as e:
        pass

    _LOGGER.error(f"Station connect error: {e}")
    return None


UA = "Mozilla/5.0 (Windows NT 10.0; rv:40.0) Gecko/20100101 Firefox/40.0"
RE_CSRF = re.compile('"csrfToken2":"(.+?)"')


class Quasar:
    """Класс для работы с Квазар API. Авторизация через Яндекс.Паспорт и
    сохранение сессии в куки.
    """

    def __init__(self, username: str, password: str, cookie_path: str):
        self._username = username
        self._password = password
        self._cookie_path = cookie_path

        self.session = requests.Session()
        self.session.headers = {'User-Agent': UA}

        self.load_cookies()

    def load_cookies(self):
        """Загружает куки из файла."""
        if os.path.isfile(self._cookie_path):
            with open(self._cookie_path, 'rb') as f:
                cookies = pickle.loads(f.read())
                self.session.cookies.update(cookies)

    def save_cookies(self):
        """Сохраняет куки в файл."""
        with open(self._cookie_path, 'wb') as f:
            pickle.dump(self.session.cookies, f)

    def get_csrf_token(self) -> Optional[str]:
        """Проверяет есть ли авторизация в Яндексе и если её нет -
        авторизуется. Возвращает CSRF-токен, необходимый для POST-заросов.
        """
        r = self.session.get('https://quasar.yandex.ru/skills/')

        if r.url.endswith('promo'):
            _LOGGER.info("Login to Yandex Passport")

            self.session.get('https://passport.yandex.ru/')
            self.session.post('https://passport.yandex.ru/passport', params={
                'mode': 'auth', 'retpath': 'https://yandex.ru'
            }, data={
                'login': self._username, 'passwd': self._password
            })
            r = self.session.get('https://quasar.yandex.ru/skills/')

            self.save_cookies()

        else:
            _LOGGER.debug("Already login Yandex")

        m = RE_CSRF.search(r.text)
        if m:
            _LOGGER.debug(f"CSRF Token: {m[1]}")
            return m[1]
        else:
            _LOGGER.error("Can't get CSRF Token")
            return None

    def get_device_config(self, config: dict):
        self.get_csrf_token()

        r = self.session.get(
            'https://quasar.yandex.ru/get_device_config',
            params={'device_id': config['id'], 'platform': config['platform']})
        _LOGGER.debug(r.text)

        res = r.json()
        if res.get('status') == 'error':
            _LOGGER.error(res['message'])
            return None
        else:
            return res['config']

    def set_device_config(self, config: dict, quasar_config: dict):
        csrf = self.get_csrf_token()
        r = self.session.post(
            'https://quasar.yandex.ru/set_device_config',
            params={'device_id': config['id'], 'platform': config['platform']},
            headers={'x-csrf-token': csrf},
            json=quasar_config)
        _LOGGER.debug(r.text)
