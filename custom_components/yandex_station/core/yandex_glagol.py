import asyncio
import ipaddress
import json
import logging
import time
import uuid
from asyncio import Future
from typing import Callable, Optional, Dict

from aiohttp import ClientWebSocketResponse, WSMsgType, ClientConnectorError

from custom_components.yandex_station.core.yandex_session import YandexSession
from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange

_LOGGER = logging.getLogger(__name__)


class YandexGlagol:
    """Класс для работы с колонкой по локальному протоколу."""
    device_token = None
    url: Optional[str] = None
    ws: Optional[ClientWebSocketResponse] = None

    # next_ping_ts = 0
    # keep_task: Task = None
    update_handler: Callable = None

    waiters: Dict[str, Future] = {}

    def __init__(self, session: YandexSession, device: dict):
        self.session = session
        self.device = device
        self.loop = asyncio.get_event_loop()

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
            if self.ws:
                await self.ws.close()

    async def stop(self):
        self.debug("Останавливаем локальное подключение")
        self.url = None
        if self.ws:
            await self.ws.close()

    async def _connect(self, fails: int):
        self.debug("Локальное подключение")

        try:
            if not self.device_token:
                self.device_token = await self.get_device_token()

            self.ws = await self.session.ws_connect(self.url, heartbeat=55,
                                                    ssl=False)
            await self.ping(command="softwareVersion")

            if not self.ws.closed:
                fails = 0

            # if not self.keep_task or self.keep_task.done():
            #     self.keep_task = self.loop.create_task(self._keep_connection())

            async for msg in self.ws:
                if msg.type == WSMsgType.TEXT:
                    # _LOGGER.debug("update")

                    # Большая станция в режиме idle шлёт статус раз в 5 секунд,
                    # в режиме playing шлёт чаще раза в 1 секунду
                    # self.next_ping_ts = time.time() + 6

                    data = json.loads(msg.data)

                    response = None

                    resp = data.get('vinsResponse')
                    if resp:
                        try:
                            # payload only in yandex module
                            card = resp['payload']['response']['card'] \
                                if 'payload' in resp \
                                else resp['response']['card']

                            if card:
                                response = card

                        except Exception as e:
                            _LOGGER.debug(f"Response error: {e}")

                    request_id = data.get('requestId')
                    if request_id in self.waiters:
                        self.waiters[request_id].set_result(response)

                    self.update_handler(data)

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
            if self.ws and not self.ws.closed:
                await self.ws.close()
            return

        except:
            _LOGGER.exception(f"{self.name} | Station connect")
            fails += 1

        # возвращаемся в облачный режим
        self.update_handler(None)

        # останавливаем попытки
        if not self.url:
            return

        if fails:
            # 30s, 60s, ... 5 min
            timeout = 30 * min(fails, 10)
            self.debug(f"Таймаут до следующего подключения {timeout}")
            await asyncio.sleep(timeout)

        asyncio.create_task(self._connect(fails))

    # async def _keep_connection(self):
    #     _LOGGER.debug("Start keep connection task")
    #     while not self.ws.closed:
    #         await asyncio.sleep(1)
    #         if time.time() > self.next_ping_ts:
    #             await self.ping()

    async def ping(self, command="ping"):
        # _LOGGER.debug("ping")
        try:
            await self.ws.send_json({
                'conversationToken': self.device_token,
                'id': str(uuid.uuid4()),
                'payload': {'command': command},
                'sentTime': int(round(time.time() * 1000)),
            })
        except:
            pass

    async def send(self, payload: dict) -> Optional[dict]:
        _LOGGER.debug(f"{self.name} => local | {payload}")

        request_id = str(uuid.uuid4())

        try:
            await self.ws.send_json({
                'conversationToken': self.device_token,
                'id': request_id,
                'payload': payload,
                'sentTime': int(round(time.time() * 1000)),
            })

            self.waiters[request_id] = self.loop.create_future()

            # limit future wait time
            await asyncio.wait_for(self.waiters[request_id], 5)

            # self.next_ping_ts = time.time() + 0.5

            return self.waiters.pop(request_id).result()

        except asyncio.TimeoutError:
            _ = self.waiters.pop(request_id, None)

        except Exception as e:
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
        try:
            info = zeroconf.get_service_info(service_type, name)
        except Exception as e:
            _LOGGER.warning("Can't get zeroconf info", exc_info=e)
            return

        if not info or len(info.addresses) == 0:
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
