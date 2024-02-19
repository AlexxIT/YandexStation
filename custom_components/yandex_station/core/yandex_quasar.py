import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from aiohttp import WSMsgType

from .yandex_session import YandexSession

_LOGGER = logging.getLogger(__name__)

IOT_TYPES = {
    "on": "devices.capabilities.on_off",
    "temperature": "devices.capabilities.range",
    "fan_speed": "devices.capabilities.mode",
    "thermostat": "devices.capabilities.mode",
    "program": "devices.capabilities.mode",
    "heat": "devices.capabilities.mode",
    "volume": "devices.capabilities.range",
    "pause": "devices.capabilities.toggle",
    "mute": "devices.capabilities.toggle",
    "channel": "devices.capabilities.range",
    "input_source": "devices.capabilities.mode",
    "brightness": "devices.capabilities.range",
    "color": "devices.capabilities.color_setting",
    "work_speed": "devices.capabilities.mode",
    "humidity": "devices.capabilities.range",
    "ionization": "devices.capabilities.toggle",
    "backlight": "devices.capabilities.toggle",
    # kettle:
    "keep_warm": "devices.capabilities.toggle",
    "tea_mode": "devices.capabilities.mode",
    # don't work
    "hsv": "devices.capabilities.color_setting",
    "rgb": "devices.capabilities.color_setting",
    "temperature_k": "devices.capabilities.color_setting",
}

MASK_EN = "0123456789abcdef-"
MASK_RU = "оеаинтсрвлкмдпуяы"

URL_USER = "https://iot.quasar.yandex.ru/m/user"
URL_V3_USER = "https://iot.quasar.yandex.ru/m/v3/user"


def encode(uid: str) -> str:
    """Кодируем UID в рус. буквы. Яндекс привередливый."""
    return "ХА " + "".join([MASK_RU[MASK_EN.index(s)] for s in uid])


def decode(uid: str) -> Optional[str]:
    """Раскодируем UID из рус.букв."""
    if not uid.startswith("ХА "):
        return None
    try:
        return "".join([MASK_EN[MASK_RU.index(s)] for s in uid[3:]])
    except Exception:
        return None


def parse_scenario(data: dict) -> dict:
    result = {
        k: v
        for k, v in data.items()
        if k in ("name", "icon", "effective_time", "settings")
    }
    result["triggers"] = [parse_trigger(i) for i in data["triggers"]]
    result["steps"] = [parse_step(i) for i in data["steps"]]
    return result


def parse_trigger(data: dict) -> dict:
    result = {k: v for k, v in data.items() if k == "filters"}

    value = data["trigger"]["value"]
    if isinstance(value, dict):
        value = {
            k: v
            for k, v in value.items()
            if k in ("instance", "property_type", "condition")
        }
        value["device_id"] = data["trigger"]["value"]["device"]["id"]

    result["trigger"] = {"type": data["trigger"]["type"], "value": value}
    return result


def parse_step(data: dict) -> dict:
    params = data["parameters"]
    return {
        "type": data["type"],
        "parameters": {
            "requested_speaker_capabilities": params["requested_speaker_capabilities"],
            "launch_devices": [parse_device(i) for i in params["launch_devices"]],
        },
    }


def parse_device(data: dict) -> dict:
    return {
        "id": data["id"],
        "capabilities": [
            {"type": i["type"], "state": i["state"]} for i in data["capabilities"]
        ],
        "directives": data["directives"],
    }


class Dispatcher:
    dispatcher: dict[str, list] = None

    def __init__(self):
        self.dispatcher = {}

    def subscribe_update(self, signal: str, target):
        targets = self.dispatcher.setdefault(signal, [])
        if target not in targets:
            targets.append(target)
        return lambda: targets.remove(target)

    def dispatch_update(self, signal: str, message: dict):
        if signal not in self.dispatcher:
            return
        for target in self.dispatcher[signal]:
            target(message)


class YandexQuasar(Dispatcher):
    # all devices
    devices: list[dict] = None
    scenarios: list[dict] = None
    online_updated: asyncio.Event = None
    updates_task: asyncio.Task = None

    def __init__(self, session: YandexSession):
        super().__init__()
        self.session = session
        self.online_updated = asyncio.Event()
        self.online_updated.set()

    @property
    def hass_id(self):
        for device in self.devices:
            if device["name"] == "Yandex Intents":
                return device["id"]
        return None

    async def init(self):
        """Основная функция. Возвращает список колонок."""
        _LOGGER.debug("Получение списка устройств.")

        r = await self.session.get(f"{URL_V3_USER}/devices")
        resp = await r.json()
        assert resp["status"] == "ok", resp

        self.devices = []

        for house in resp["households"]:
            if "sharing_info" in house:
                continue
            self.devices += house["all"]

        await self.load_scenarios()

    @property
    def speakers(self):
        return [
            d for d in self.devices if d.get("quasar_info") and d.get("capabilities")
        ]

    @property
    def modules(self):
        # modules don't have cloud scenarios
        return [
            d
            for d in self.devices
            if d.get("quasar_info") and not d.get("capabilities")
        ]

    async def load_speakers(self) -> list:
        speakers = self.speakers

        # Яндекс начали добавлять device_id и platform с полным списком
        # устройств
        # for speaker in speakers:
        #     await self.load_speaker_config(speaker)

        scenarios = {decode(d["name"]): d for d in self.scenarios if decode(d["name"])}

        for speaker in speakers:
            device_id: str = speaker["id"]

            try:
                scenario = next(
                    v for k, v in scenarios.items() if device_id.startswith(k)
                )
            except StopIteration:
                scenario = await self.add_scenario(device_id)

            speaker["scenario_id"] = scenario["id"]

        return speakers

    async def load_speaker_config(self, device: dict):
        """Загружаем device_id и platform для колонок. Они не приходят с полным
        списком устройств.
        """
        r = await self.session.get(f"{URL_USER}/devices/{device['id']}/configuration")
        resp = await r.json()
        assert resp["status"] == "ok", resp
        # device_id and platform
        device.update(resp["quasar_info"])

    async def load_scenarios(self) -> dict:
        """Получает список сценариев, которые мы ранее создали."""
        r = await self.session.get(f"{URL_USER}/scenarios")
        resp = await r.json()
        assert resp["status"] == "ok", resp

        self.scenarios = resp["scenarios"]

    async def update_scenario(self, name: str):
        # check if we known scenario name
        sid = next((i["id"] for i in self.scenarios if i["name"] == name), None)

        if sid is None:
            # reload scenarios list
            await self.load_scenarios()
            sid = next(i["id"] for i in self.scenarios if i["name"] == name)

        # load scenario info
        r = await self.session.get(
            f"https://iot.quasar.yandex.ru/m/v3/user/scenarios/{sid}/edit"
        )
        resp = await r.json()
        assert resp["status"] == "ok"

        # convert to scenario patch
        payload = parse_scenario(resp["scenario"])
        r = await self.session.put(
            f"https://iot.quasar.yandex.ru/m/v3/user/scenarios/{sid}", json=payload
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

    async def add_scenario(self, device_id: str) -> dict:
        """Добавляет сценарий-пустышку."""
        name = encode(device_id)
        payload = {
            "name": name[:25],
            "icon": "home",
            "triggers": [{"type": "scenario.trigger.voice", "value": name[3:]}],
            "steps": [
                {
                    "type": "scenarios.steps.actions",
                    "parameters": {
                        "requested_speaker_capabilities": [],
                        "launch_devices": [
                            {
                                "id": device_id,
                                "capabilities": [
                                    {
                                        "type": "devices.capabilities.quasar.server_action",
                                        "state": {
                                            "instance": "phrase_action",
                                            "value": "пустышка",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                }
            ],
        }
        r = await self.session.post(f"{URL_USER}/scenarios", json=payload)
        resp = await r.json()
        if resp["status"] != "ok":
            print()
        assert resp["status"] == "ok", resp
        return {"id": resp["scenario_id"]}

    async def add_intent(self, name: str, text: str, num: int):
        speaker = (
            [
                {
                    "type": "devices.capabilities.quasar.server_action",
                    "state": {"instance": "phrase_action", "value": text},
                }
            ]
            if text
            else [
                {
                    "type": "devices.capabilities.quasar.server_action",
                    "state": {
                        "instance": "text_action",
                        "value": "Yandex Intents громкость 100",
                    },
                }
            ]
        )

        payload = {
            "name": name[:25],
            "icon": "home",
            "triggers": [{"type": "scenario.trigger.voice", "value": name}],
            "steps": [
                {
                    "type": "scenarios.steps.actions",
                    "parameters": {
                        "requested_speaker_capabilities": speaker,
                        "launch_devices": [
                            {
                                "id": self.hass_id,
                                "capabilities": [
                                    {
                                        "type": "devices.capabilities.range",
                                        "state": {
                                            "instance": "volume",
                                            "relative": False,
                                            "value": num,
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                }
            ],
        }
        r = await self.session.post(f"{URL_USER}/scenarios", json=payload)
        resp = await r.json()
        assert resp["status"] == "ok", resp

    async def send(self, device: dict, text: str, is_tts: bool = False):
        """Запускает сценарий на выполнение команды или TTS."""
        # skip send for yandex modules
        if "scenario_id" not in device:
            return
        _LOGGER.debug(f"{device['name']} => cloud | {text}")

        action = "phrase_action" if is_tts else "text_action"
        name = encode(device["id"])
        payload = {
            "name": name[:25],
            "icon": "home",
            "triggers": [{"type": "scenario.trigger.voice", "value": name[3:]}],
            "steps": [
                {
                    "type": "scenarios.steps.actions",
                    "parameters": {
                        "requested_speaker_capabilities": [],
                        "launch_devices": [
                            {
                                "id": device["id"],
                                "capabilities": [
                                    {
                                        "type": "devices.capabilities.quasar.server_action",
                                        "state": {"instance": action, "value": text},
                                    }
                                ],
                            }
                        ],
                    },
                }
            ],
        }

        sid = device["scenario_id"]

        r = await self.session.put(f"{URL_USER}/scenarios/{sid}", json=payload)
        resp = await r.json()
        assert resp["status"] == "ok", resp

        r = await self.session.post(f"{URL_USER}/scenarios/{sid}/actions")
        resp = await r.json()
        assert resp["status"] == "ok", resp

    async def load_local_speakers(self):
        """Загружает список локальных колонок. Не используется."""
        try:
            r = await self.session.get("https://quasar.yandex.net/glagol/device_list")
            resp = await r.json()
            return [
                {"device_id": d["id"], "name": d["name"], "platform": d["platform"]}
                for d in resp["devices"]
            ]

        except:
            _LOGGER.exception("Load local speakers")
            return None

    async def get_device_config(self, device: dict) -> dict:
        payload = {
            "device_id": device["quasar_info"]["device_id"],
            "platform": device["quasar_info"]["platform"],
        }
        r = await self.session.get(
            "https://quasar.yandex.ru/get_device_config", params=payload
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp
        return resp["config"]

    async def set_device_config(self, device: dict, device_config: dict):
        _LOGGER.debug(f"Меняем конфиг станции: {device_config}")

        payload = {
            "device_id": device["quasar_info"]["device_id"],
            "platform": device["quasar_info"]["platform"],
        }
        r = await self.session.post(
            "https://quasar.yandex.ru/set_device_config",
            params=payload,
            json=device_config,
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

    async def get_device(self, deviceid: str):
        r = await self.session.get(f"{URL_USER}/devices/{deviceid}")
        resp = await r.json()
        assert resp["status"] == "ok", resp
        return resp

    async def device_action(self, deviceid: str, instance: str, value):
        action = {
            "type": IOT_TYPES[instance],
            "state": {"instance": instance, "value": value},
        }
        r = await self.session.post(
            f"{URL_USER}/devices/{deviceid}/actions", json={"actions": [action]}
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

        # update device state
        device = await self.get_device(deviceid)
        self.dispatch_update(deviceid, device)

    async def device_actions(self, deviceid: str, **kwargs):
        _LOGGER.debug(f"Device action: {kwargs}")

        actions = []
        for k, v in kwargs.items():
            type_ = (
                "devices.capabilities.custom.button" if k.isdecimal() else IOT_TYPES[k]
            )
            state = (
                {"instance": k, "value": v, "relative": True}
                if k in ("volume", "channel")
                else {"instance": k, "value": v}
            )
            actions.append({"type": type_, "state": state})

        r = await self.session.post(
            f"{URL_USER}/devices/{deviceid}/actions", json={"actions": actions}
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

        # update device state
        device = await self.get_device(deviceid)
        self.dispatch_update(deviceid, device)

    async def update_online_stats(self):
        if not self.online_updated.is_set():
            await self.online_updated.wait()
            return

        self.online_updated.clear()

        # _LOGGER.debug(f"Update speakers online status")

        try:
            r = await self.session.get("https://quasar.yandex.ru/devices_online_stats")
            resp = await r.json()
            assert resp["status"] == "ok", resp
        except:
            return
        finally:
            self.online_updated.set()

        for speaker in resp["items"]:
            for device in self.devices:
                if (
                    "quasar_info" not in device
                    or device["quasar_info"]["device_id"] != speaker["id"]
                ):
                    continue
                device["online"] = speaker["online"]
                break

    async def connect(self):
        r = await self.session.get("https://iot.quasar.yandex.ru/m/v3/user/devices")
        resp = await r.json()
        assert resp["status"] == "ok", resp

        for house in resp["households"]:
            if "sharing_info" in house:
                continue
            for device in house["all"]:
                self.dispatch_update(device["id"], device)

        ws = await self.session.ws_connect(resp["updates_url"], heartbeat=60)
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                break
            resp = msg.json()
            # "ping", "update_scenario_list"
            operation = resp.get("operation")
            if operation == "update_states":
                try:
                    resp = json.loads(resp["message"])
                    for device in resp["updated_devices"]:
                        self.dispatch_update(device["id"], device)
                except Exception as e:
                    _LOGGER.debug(f"Parse quasar update error: {msg.data}", exc_info=e)

            elif operation == "update_scenario_list":
                if '"source":"create_scenario_launch"' in resp["message"]:
                    asyncio.create_task(self.get_voice_trigger(1))

    async def get_voice_trigger(self, retries: int = 0):
        try:
            # 1. Get all scenarios history
            r = await self.session.get(
                "https://iot.quasar.yandex.ru/m/user/scenarios/history"
            )
            raw = await r.json()

            # 2. Search latest scenario with voice trigger
            scenario = next(
                s
                for s in raw["scenarios"]
                if s["trigger_type"] == "scenario.trigger.voice"
            )

            # 3. Check if scenario too old
            d1 = datetime.strptime(r.headers["Date"], "%a, %d %b %Y %H:%M:%S %Z")
            d2 = datetime.strptime(scenario["launch_time"], "%Y-%m-%dT%H:%M:%SZ")
            dt = (d1 - d2).total_seconds()
            if dt > 5:
                # try to get history once more
                if retries:
                    await self.get_voice_trigger(retries - 1)
                return

            # 4. Get speakers from launch devices
            r = await self.session.get(
                f"https://iot.quasar.yandex.ru/m/v3/user/launches/{scenario['id']}/edit"
            )
            raw = await r.json()

            for step in raw["launch"]["steps"]:
                for device in step["parameters"]["launch_devices"]:
                    # 5. Check if speaker device
                    if "quasar_info" not in device:
                        continue
                    device["scenario_name"] = raw["launch"]["name"]
                    self.dispatch_update(device["id"], device)

        except Exception as e:
            _LOGGER.debug("Can't get voice scenario", exc_info=e)

    async def run_forever(self):
        while not self.session.session.closed:
            try:
                await self.connect()
            except Exception as e:
                _LOGGER.debug("Quasar update error", exc_info=e)
            await asyncio.sleep(30)

    def start(self):
        self.updates_task = asyncio.create_task(self.run_forever())

    def stop(self):
        if self.updates_task:
            self.updates_task.cancel()
        self.dispatcher.clear()

    async def set_account_config(self, key: str, value):
        kv = ACCOUNT_CONFIG.get(key)
        assert kv and value in kv["values"], f"{key}={value}"

        if kv.get("api") == "user/settings":
            # https://iot.quasar.yandex.ru/m/user/settings
            r = await self.session.post(
                f"{URL_USER}/settings", json={kv["key"]: kv["values"][value]}
            )

        else:
            r = await self.session.get("https://quasar.yandex.ru/get_account_config")
            resp = await r.json()
            assert resp["status"] == "ok", resp

            payload: dict = resp["config"]
            payload[kv["key"]] = kv["values"][value]

            r = await self.session.post(
                "https://quasar.yandex.ru/set_account_config", json=payload
            )

        resp = await r.json()
        assert resp["status"] == "ok", resp


BOOL_CONFIG = {"да": True, "нет": False}
ACCOUNT_CONFIG = {
    "без лишних слов": {
        "api": "user/settings",
        "key": "iot",
        "values": {
            "да": {"response_reaction_type": "sound"},
            "нет": {"response_reaction_type": "nlg"},
        },
    },
    "ответить шепотом": {
        "api": "user/settings",
        "key": "tts_whisper",
        "values": BOOL_CONFIG,
    },
    "анонсировать треки": {
        "api": "user/settings",
        "key": "music",
        "values": {
            "да": {"announce_tracks": True},
            "нет": {"announce_tracks": False},
        },
    },
    "скрывать названия товаров": {
        "api": "user/settings",
        "key": "order",
        "values": {
            "да": {"hide_item_names": True},
            "нет": {"hide_item_names": False},
        },
    },
    "звук активации": {"key": "jingle", "values": BOOL_CONFIG},  # /get_account_config
    "одним устройством": {
        "key": "smartActivation",  # /get_account_config
        "values": BOOL_CONFIG,
    },
    "понимать детей": {
        "key": "useBiometryChildScoring",  # /get_account_config
        "values": BOOL_CONFIG,
    },
    "рассказывать о навыках": {
        "key": "aliceProactivity",  # /get_account_config
        "values": BOOL_CONFIG,
    },
    "взрослый голос": {
        "key": "contentAccess",  # /get_account_config
        "values": {
            "умеренный": "medium",
            "семейный": "children",
            "безопасный": "safe",
            "без ограничений": "without",
        },
    },
    "детский голос": {
        "key": "childContentAccess",  # /get_account_config
        "values": {
            "безопасный": "safe",
            "семейный": "children",
        },
    },
    "имя": {
        "key": "spotter",  # /get_account_config
        "values": {
            "алиса": "alisa",
            "яндекс": "yandex",
        },
    },
}
