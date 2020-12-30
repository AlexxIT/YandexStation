import asyncio
import ipaddress
import json
import logging
import time
import uuid
from typing import Callable, Optional

from aiohttp import ClientWebSocketResponse, WSMsgType, ClientConnectorError

from custom_components.yandex_station.core.yandex_session import YandexSession
from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange

_LOGGER = logging.getLogger(__name__)


class YandexGlagol:
    """Класс для работы с колонкой по локальному протоколу."""
    device_token = None
    url: Optional[str] = None
    ws: Optional[ClientWebSocketResponse] = None
    wait_response = False

    update_handler: Callable = None
    response_handler: Callable = None

    def __init__(self, session: YandexSession, device: dict):
        self.session = session
        self.device = device
        self.new_state = asyncio.Event()

    def debug(self, text: str):
        _LOGGER.debug(f"{self.device['name']} | {text}")

    def is_device(self, device: str):
        return (self.device['quasar_info']['device_id'] == device or
                self.device['name'] == device)

    @property
    def name(self):
        return self.device['name']

    async def get_device_token(self):
        self.debug("Обновление токена устройства")

        payload = {
            'device_id': self.device['quasar_info']['device_id'],
            'platform': self.device['quasar_info']['platform']
        }
        r = await self.session.get(
            'https://quasar.yandex.net/glagol/token', params=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        return resp['token']

    async def start_or_restart(self):
        # first time
        if not self.url:
            self.url = f"wss://{self.device['host']}:{self.device['port']}"
            asyncio.create_task(self._connect(0))

        # check IP change
        elif self.device['host'] not in self.url:
            self.debug("Обновление IP-адреса устройства")
            self.url = f"wss://{self.device['host']}:{self.device['port']}"
            # force close session
            await self.ws.close()

    async def stop(self):
        self.debug("Останавливаем локальное подключение")
        self.url = None
        await self.ws.close()

    async def _connect(self, fails: int):
        self.debug("Локальное подключение")

        if not self.device_token:
            self.device_token = await self.get_device_token()

        try:
            self.ws = await self.session.ws_connect(self.url, heartbeat=55,
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
                                await self.response_handler(card, request_id)

                        except Exception as e:
                            _LOGGER.debug(f"Response error: {e}")

                    if self.wait_response:
                        if resp:
                            self.wait_response = False
                        continue

                    # TODO: проверить, что это всё ещё нужно
                    self.new_state.set()

                    await self.update_handler(data)

            # TODO: find better place
            self.device_token = None

        except ClientConnectorError as e:
            self.debug(f"Ошибка подключения: {e.args}")
            fails += 1

        except (asyncio.CancelledError, RuntimeError) as e:
            # сюда попадаем при остановке HA
            if isinstance(e, RuntimeError):
                assert e.args[0] == "Session is closed", e.args

            self.debug(f"Останавливаем подключение: {e}")
            if not self.ws.closed:
                await self.ws.close()
            return

        except:
            _LOGGER.exception(f"{self.name} | Station connect")
            fails += 1

        # возвращаемся в облачный режим
        await self.update_handler(None)

        # останавливаем попытки
        if not self.url:
            return

        # вдруг ждём - сбросим
        self.new_state.set()

        if fails:
            # 15, 30, 60, 120, 240, 480
            timeout = 15 * 2 ** min(fails - 1, 5)
            self.debug(f"Таймаут до следующего подключения {timeout}")
            await asyncio.sleep(timeout)

        asyncio.create_task(self._connect(fails))

    async def send(self, payload: dict, request_id: str = None):
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

    async def reset_session(self):
        payload = {'command': 'serverAction', 'serverActionEventPayload': {
            'type': 'server_action', 'name': 'on_reset_session'}}
        await self.send(payload)


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
