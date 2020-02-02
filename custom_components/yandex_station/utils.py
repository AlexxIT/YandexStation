import json
import logging
import os
from ssl import SSLContext
from functools import lru_cache
from typing import Optional

import requests
import websockets

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


@lru_cache()
def get_device_token(yandex_token: str, device_id: str,
                     device_platform: str) -> str:
    r = requests.get('https://quasar.yandex.net/glagol/token', params={
        'device_id': device_id,
        'platform': device_platform
    }, headers={'Authorization': f"Oauth {yandex_token}"})
    _LOGGER.debug(r.text)
    return r.json()['token']


async def send_to_station(device: dict, message: dict = None):
    device_token = get_device_token(device['yandex_token'], device['id'],
                                    device['platform'])

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

    except Exception as e:
        _LOGGER.error(f"Station connect error: {e}")

        return None
