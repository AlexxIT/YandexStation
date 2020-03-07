import asyncio
import json
import logging
import os
import pickle
import re
from functools import lru_cache
from ssl import SSLContext
from typing import Optional

import requests
from aiohttp import ClientSession
from homeassistant.components.media_player import DOMAIN as DOMAIN_MP
from homeassistant.helpers.entity_component import DATA_INSTANCES

import websockets

_LOGGER = logging.getLogger(__name__)

# Thanks to https://github.com/MarshalX/yandex-music-api/
CLIENT_ID = '23cabbbdc6cd418abb4b39c32c41195d'
CLIENT_SECRET = '53bc75238f0c4d08a118e51fe9203300'


def init_zeroconf_singleton(hass):
    """Generate only one Zeroconf. Component must be loaded before Zeroconf."""
    from homeassistant.components import zeroconf
    if isinstance(zeroconf.Zeroconf, type):
        def zeroconf_singleton():
            if 'zeroconf' not in hass.data:
                from zeroconf import Zeroconf
                _LOGGER.debug("Generate zeroconf singleton")
                hass.data['zeroconf'] = Zeroconf()
            else:
                _LOGGER.debug("Use zeroconf singleton")
            return hass.data['zeroconf']

        _LOGGER.debug("Init zeroconf singleton")
        zeroconf.Zeroconf = zeroconf_singleton


def load_token(filename: str) -> Optional[str]:
    if os.path.isfile(filename):
        with open(filename, 'rt', encoding='utf-8') as f:
            return f.read()
    return None


def save_token(filename: str, token: str):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(token)


async def get_yandex_token(username: str, password: str,
                           session: ClientSession) -> str:
    r = await session.post('https://oauth.yandex.ru/token', data={
        'grant_type': 'password',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'username': username,
        'password': password
    }, headers={
        'User-Agent': 'Yandex-Music-API',
        'X-Yandex-Music-Client': 'WindowsPhone/3.20',
    })
    _LOGGER.debug(await r.text())

    resp = await r.json()
    return resp['access_token']


@lru_cache()
async def get_devices(yandex_token: str, session: ClientSession) -> dict:
    r = await session.get('https://quasar.yandex.net/glagol/device_list',
                          headers={'Authorization': f"Oauth {yandex_token}"})
    _LOGGER.debug(await r.text())

    resp = await r.json()
    return resp['devices']


class Glagol:
    def __init__(self):
        self._config = None
        self.device_token = None
        self.ws: Optional[websockets.connect] = None
        self.new_state: Optional[asyncio.Event] = None
        self.wait_response = False

    def is_device(self, device: str):
        return self._config['id'] == device or self._config['name'] == device

    async def refresh_device_token(self, session: ClientSession):
        _LOGGER.debug(f"Refresh device token {self._config['id']}")
        r = await session.get(
            'https://quasar.yandex.net/glagol/token', params={
                'device_id': self._config['id'],
                'platform': self._config['platform']
            },
            headers={
                'Authorization': f"Oauth {self._config['yandex_token']}"
            })
        _LOGGER.debug(await r.text())

        resp = await r.json()
        self.device_token = resp['token']

    async def run_forever(self, session: ClientSession):
        self.new_state = asyncio.Event()

        while True:
            _LOGGER.debug(f"Restart status loop {self._config['id']}")

            if not self.device_token:
                await self.refresh_device_token(session)

            uri = f"wss://{self._config['host']}:{self._config['port']}"
            try:
                self.ws = await websockets.connect(uri, ssl=SSLContext())
                # врядли это API работает, но пусть будет
                await self.ws.send(json.dumps({
                    'conversationToken': self.device_token,
                    'payload': {'command': 'subscribeStatus', 'interval': 5}
                }))

                # сбросим на всяк пожарный
                self.wait_response = False

                while True:
                    res = await self.ws.recv()
                    data = json.loads(res)

                    if self.wait_response:
                        if 'vinsResponse' in data:
                            self.wait_response = False
                        continue

                    self.new_state.set()

                    await self.update(data)

            except websockets.ConnectionClosed as e:
                if e.code == 4000:
                    self.device_token = None
                    continue
                elif e.code == 4001:
                    # no pong for long
                    continue

                _LOGGER.error(f"Station connect error: {e}")

            except Exception as e:
                _LOGGER.error(f"Station connect error: {e}")

            await asyncio.sleep(30)

    async def send_to_station(self, payload: dict):
        # _LOGGER.debug(f"Send: {payload}")

        if payload.get('command') in ('sendText', 'serverAction'):
            self.wait_response = True

        await self.ws.send(json.dumps({
            'conversationToken': self.device_token,
            'payload': payload
        }))

        # block until new state receive
        self.new_state.clear()
        await self.new_state.wait()

    async def update(self, data: dict):
        pass


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


def update_form(name: str, **kwargs):
    return {
        'command': 'serverAction',
        'serverActionEventPayload': {
            'type': 'server_action',
            'name': 'update_form',
            'payload': {
                'form_update': {
                    'name': name,
                    'slots': [{'type': 'string', 'name': k, 'value': v}
                              for k, v in kwargs.items()]
                },
                'resubmit': True
            }
        }
    }


def find_station(hass, device: str = None) -> Optional[str]:
    """Найти станцию по ID, имени или просто первую попавшуюся."""
    from .media_player import YandexStation
    for entity in hass.data[DATA_INSTANCES][DOMAIN_MP].entities:
        if isinstance(entity, YandexStation):
            if device is None or entity.is_device(device):
                return entity.entity_id
    return None
