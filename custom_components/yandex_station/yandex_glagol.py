import asyncio
import ipaddress
import json
import logging
from typing import Callable, Optional

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType, \
    ClientConnectorError

from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange

_LOGGER = logging.getLogger(__name__)


class Glagol:
    """Класс для работы с колонкой по локальному протоколу."""
    device_token = None
    new_state: Optional[asyncio.Event] = None
    ws: Optional[ClientWebSocketResponse] = None
    wait_response = False

    def __init__(self, quasar, device: dict):
        self.quasar = quasar
        self.device = device

    def is_device(self, device: str):
        return (self.device['device_id'] == device or
                self.device['name'] == device)

    async def refresh_device_token(self, session: ClientSession):
        _LOGGER.debug(f"Обновление токена устройства: {self.device['name']}")

        payload = {
            'device_id': self.device['device_id'],
            'platform': self.device['platform']
        }
        token = self.quasar.local_token['access_token']
        r = await session.get(
            'https://quasar.yandex.net/glagol/token', params=payload,
            headers={'Authorization': f"Oauth {token}"})
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        self.device_token = resp['token']

    async def local_start(self, session: ClientSession):
        self.new_state = asyncio.Event()
        asyncio.create_task(self._connect(session))

    async def _connect(self, session: ClientSession):
        _LOGGER.debug(f"Локальное подключение: {self.device['name']}")

        if not self.device_token:
            await self.refresh_device_token(session)

        uri = f"wss://{self.device['host']}:{self.device['port']}"
        try:
            self.ws = await session.ws_connect(uri, heartbeat=55, ssl=False)
            await self.ws.send_json({
                'conversationToken': self.device_token,
                'payload': {'command': 'ping'}
            })

            # сбросим на всяк пожарный
            self.wait_response = False

            async for msg in self.ws:
                if msg.type == WSMsgType.TEXT:
                    data = json.loads(msg.data)

                    if self.wait_response:
                        if 'vinsResponse' in data:
                            self.wait_response = False
                        continue

                    self.new_state.set()

                    await self.update(data)

                elif msg.type == WSMsgType.CLOSED:
                    _LOGGER.debug(f"Cloud WS Closed: {msg.data}")
                    break

                elif msg.type == WSMsgType.ERROR:
                    _LOGGER.debug(f"Cloud WS Error: {msg.data}")
                    break

        except ClientConnectorError as e:
            _LOGGER.error(f"Station connect error [{e.errno}] {e}")
            await asyncio.sleep(30)

        except:
            _LOGGER.exception(f"Station connect")
            await asyncio.sleep(30)

        asyncio.create_task(self._connect(session))

    async def send_to_station(self, payload: dict):
        # _LOGGER.debug(f"Send: {payload}")

        if payload.get('command') in ('sendText', 'serverAction'):
            self.wait_response = True

        try:
            await self.ws.send_json({
                'conversationToken': self.device_token,
                'payload': payload
            })

            # block until new state receive
            self.new_state.clear()
            await self.new_state.wait()

        except Exception as e:
            self.wait_response = False

            _LOGGER.error(e)

    async def update(self, data: dict):
        pass


class YandexIOListener:
    add_handlerer = None
    processed = []
    zeroconf = Zeroconf()

    def __init__(self, loop):
        self.loop = loop

    def start(self, handlerer: Callable):
        self.add_handlerer = handlerer

        ServiceBrowser(self.zeroconf, '_yandexio._tcp.local.',
                       handlers=[self._zeroconf_handler])

    def stop(self, *args):
        self.zeroconf.close()

    def _zeroconf_handler(self, zeroconf: Zeroconf, service_type: str,
                          name: str, state_change: ServiceStateChange):
        if state_change != ServiceStateChange.Added:
            return

        info = zeroconf.get_service_info(service_type, name)
        properties = {
            k.decode(): v.decode() if isinstance(v, bytes) else v
            for k, v in info.properties.items()
        }

        device_id = properties['deviceId']
        if device_id in self.processed:
            return

        self.processed.append(device_id)

        coro = self.add_handlerer({
            'device_id': device_id,
            'platform': properties['platform'],
            'host': str(ipaddress.ip_address(info.addresses[0])),
            'port': info.port
        })
        self.loop.create_task(coro)
