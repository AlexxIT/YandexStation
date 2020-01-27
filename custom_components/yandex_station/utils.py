import json
import os
import ssl
from functools import lru_cache
from typing import Optional

import requests
import websocket

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

    return r.json()['access_token']


@lru_cache()
def get_devices(yandex_token: str) -> list:
    r = requests.get('https://quasar.yandex.net/glagol/device_list',
                     headers={'Authorization': f"Oauth {yandex_token}"})
    return r.json()['devices']


@lru_cache()
def get_device_token(yandex_token: str, device: str = None) -> str:
    devices = get_devices(yandex_token)

    if device:
        device = next(p for p in devices
                      if p['id'] == device or p['name'] == device)
    else:
        device = devices[0]

    r = requests.get('https://quasar.yandex.net/glagol/token', params={
        'device_id': device['id'],
        'platform': device['platform']
    }, headers={'Authorization': f"Oauth {yandex_token}"})

    return r.json()['token']


def send_to_station(yandex_token: str, device: str, host: str, message: dict):
    device_token = get_device_token(yandex_token, device)

    ws = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
    ws.connect(f"wss://{host}:1961")
    ws.send(json.dumps({
        'conversationToken': device_token,
        'payload': message
    }))
