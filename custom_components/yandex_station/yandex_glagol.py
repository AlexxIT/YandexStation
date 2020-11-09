import asyncio
import ipaddress
import json
import logging
import time
import uuid
from typing import Callable, Optional

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType, \
    ClientConnectorError

from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange

_LOGGER = logging.getLogger(__name__)


class Glagol:
    """Класс для работы с колонкой по локальному протоколу."""
    device_token = None
    new_state: Optional[asyncio.Event] = None
    url: str = None
    ws: Optional[ClientWebSocketResponse] = None
    wait_response = False

    # локальное состояние
    local_state: Optional[dict] = None

    def __init__(self, quasar, device: dict):
        self.quasar = quasar
        self.device = device

    def is_device(self, device: str):
        return (self.device['device_id'] == device or
                self.device['name'] == device)

    @property
    def name(self):
        return self.device['name']

    async def refresh_device_token(self, session: ClientSession):
        _LOGGER.debug(f"{self.name} | Обновление токена устройства")

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
        # first time
        if not self.url:
            self.url = f"wss://{self.device['host']}:{self.device['port']}"
            self.new_state = asyncio.Event()
            asyncio.create_task(self._connect(session, 0))

        # check IP change
        elif self.device['host'] not in self.url:
            _LOGGER.debug(f"{self.name} | Обновление IP-адреса устройства")
            self.url = f"wss://{self.device['host']}:{self.device['port']}"
            # force close session
            await self.ws.close()

    async def _connect(self, session: ClientSession, fails: int):
        _LOGGER.debug(f"{self.name} | Локальное подключение")

        try:
            if not self.device_token:
                await self.refresh_device_token(session)

            self.ws = await session.ws_connect(self.url, heartbeat=55,
                                               ssl=False)
            await self.ws.send_json({
                'conversationToken': self.device_token,
                'id': str(uuid.uuid4()),
                'payload': {'command': 'ping'},
                'sentTime': int(round(time.time() * 1000)),
            })

            if not self.ws.closed:
                fails = 0

                # сбросим на всяк пожарный
                self.wait_response = False

            async for msg in self.ws:
                if msg.type == WSMsgType.TEXT:
                    data = json.loads(msg.data)

                    resp = data.get('vinsResponse')
                    if resp:
                        try:
                            # payload only in yandex module
                            card = resp['payload']['response']['card'] \
                                if 'payload' in resp \
                                else resp['response']['card']

                            if card:
                                # asyncio.create_task(self.reset_session())

                                request_id = data.get('requestId')
                                await self.response(card, request_id)

                        except Exception as e:
                            _LOGGER.debug(f"Response error: {e}")

                    if self.wait_response:
                        if resp:
                            self.wait_response = False
                        continue

                    # TODO: проверить, что это всё ещё нужно
                    self.new_state.set()

                    await self.update(data)

            self.device_token = None

        except ClientConnectorError as e:
            _LOGGER.debug(f"{self.name} | Ошибка подключения: {e.args}")
            fails += 1

        except (asyncio.CancelledError, RuntimeError) as e:
            # сюда попадаем при остановке HA
            if isinstance(e, RuntimeError):
                assert e.args[0] == "Session is closed", e.args

            _LOGGER.debug(f"{self.name} | Останавливаем подключение: {e}")
            if not self.ws.closed:
                await self.ws.close()
            return

        except:
            _LOGGER.exception(f"{self.name} | Station connect")
            fails += 1

        # возвращаемся в облачный режим
        self.local_state = None
        # вдруг ждём - сбросим
        self.new_state.set()

        if fails:
            # 15, 30, 60, 120, 240, 480
            timeout = 15 * 2 ** min(fails - 1, 5)
            _LOGGER.debug(f"{self.name} | Таймаут до следующего подключения "
                          f"{timeout}")
            await asyncio.sleep(timeout)

        asyncio.create_task(self._connect(session, fails))

    async def send_to_station(self, payload: dict, request_id: str = None):
        _LOGGER.debug(f"{self.name} => local | {payload}")

        if payload.get('command') in ('sendText', 'serverAction'):
            self.wait_response = True

        try:
            await self.ws.send_json({
                'conversationToken': self.device_token,
                'id': request_id or str(uuid.uuid4()),
                'payload': payload,
                'sentTime': int(round(time.time() * 1000)),
            })

            # block until new state receive
            self.new_state.clear()
            await self.new_state.wait()

        except Exception as e:
            self.wait_response = False

            _LOGGER.error(e)

    async def update(self, data: dict):
        pass

    async def response(self, card: dict, request_id: str):
        pass

    async def reset_session(self):
        payload = {'command': 'serverAction', 'serverActionEventPayload': {
            'type': 'server_action', 'name': 'on_reset_session'}}
        await self.send_to_station(payload)


class YandexIOListener:
    add_handlerer = None
    browser = None

    def __init__(self, loop):
        self.loop = loop

    def start(self, handlerer: Callable, zeroconf: Zeroconf):
        self.add_handlerer = handlerer
        self.browser = ServiceBrowser(zeroconf, '_yandexio._tcp.local.',
                                      handlers=[self._zeroconf_handler])

    def stop(self, *args):
        self.browser.cancel()
        self.browser.zc.close()

    def _zeroconf_handler(self, zeroconf: Zeroconf, service_type: str,
                          name: str, state_change: ServiceStateChange):
        info = zeroconf.get_service_info(service_type, name)
        if not info:
            return

        properties = {
            k.decode(): v.decode() if isinstance(v, bytes) else v
            for k, v in info.properties.items()
        }

        coro = self.add_handlerer({
            'device_id': properties['deviceId'],
            'platform': properties['platform'],
            'host': str(ipaddress.ip_address(info.addresses[0])),
            'port': info.port
        })
        self.loop.create_task(coro)
