import asyncio
import json
import logging
from datetime import datetime

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
    # climate
    "swing": "devices.capabilities.mode",
    # kettle:
    "keep_warm": "devices.capabilities.toggle",
    "tea_mode": "devices.capabilities.mode",
    # cover
    "open": "devices.capabilities.range",
    # don't work
    "hsv": "devices.capabilities.color_setting",
    "rgb": "devices.capabilities.color_setting",
    "scene": "devices.capabilities.color_setting",
    "temperature_k": "devices.capabilities.color_setting",
}

MASK_EN = "0123456789abcdef-"
MASK_RU = "оеаинтсрвлкмдпуяы"


def encode(uid: str) -> str:
    """Кодируем UID в рус. буквы. Яндекс привередливый."""
    return "".join([MASK_RU[MASK_EN.index(s)] for s in uid])


def parse_scenario(data: dict) -> dict:
    result = {
        k: v
        for k, v in data.items()
        if k in ("name", "icon", "steps", "effective_time", "settings")
    }
    result["triggers"] = [parse_trigger(i) for i in data["triggers"]]
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


def parse_device(data: dict) -> dict:
    return {
        "id": data["id"],
        "capabilities": [
            {"type": i["type"], "state": i["state"]} for i in data["capabilities"]
        ],
        "directives": data["directives"],
    }


def scenario_speaker_tts(name: str, trigger: str, device_id: str, text: str) -> dict:
    return {
        "name": name,
        "icon": "home",
        "triggers": [
            {
                "trigger": {"type": "scenario.trigger.voice", "value": trigger},
            }
        ],
        "steps": [
            {
                "type": "scenarios.steps.actions.v2",
                "parameters": {
                    "items": [
                        {
                            "id": device_id,
                            "type": "step.action.item.device",
                            "value": {
                                "id": device_id,
                                "item_type": "device",
                                "capabilities": [
                                    {
                                        "type": "devices.capabilities.quasar",
                                        "state": {
                                            "instance": "tts",
                                            "value": {"text": text},
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                },
            }
        ],
    }


def scenario_speaker_action(
    name: str, trigger: str, device_id: str, action: str
) -> dict:
    return {
        "name": name,
        "icon": "home",
        "triggers": [
            {
                "trigger": {"type": "scenario.trigger.voice", "value": trigger},
            }
        ],
        "steps": [
            {
                "type": "scenarios.steps.actions.v2",
                "parameters": {
                    "items": [
                        {
                            "id": device_id,
                            "type": "step.action.item.device",
                            "value": {
                                "id": device_id,
                                "item_type": "device",
                                "capabilities": [
                                    {
                                        "type": "devices.capabilities.quasar.server_action",
                                        "state": {
                                            "instance": "text_action",
                                            "value": action,
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                },
            }
        ],
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

    async def init(self):
        """Основная функция. Возвращает список колонок."""
        _LOGGER.debug("Получение списка устройств.")

        r = await self.session.get(
            f"https://iot.quasar.yandex.ru/m/v3/user/devices", timeout=15
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

        self.devices = []

        for house in resp["households"]:
            if "sharing_info" in house:
                continue
            self.devices.extend(
                {**device, "house_name": house["name"]} for device in house["all"]
            )

        await self.load_scenarios()
        await self.load_speakers()

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

    async def load_speakers(self):
        hashes = {}
        for scenario in self.scenarios:
            try:
                hash = scenario["triggers"][0]["value"]
                hashes[hash] = scenario["id"]
            except Exception:
                pass

        for speaker in self.speakers:
            device_id: str = speaker["id"]
            hash = encode(device_id)
            speaker["scenario_id"] = (
                hashes[hash]
                if hash in hashes
                else await self.add_scenario(device_id, hash)
            )

    async def load_speaker_config(self, device: dict):
        """Загружаем device_id и platform для колонок. Они не приходят с полным
        списком устройств.
        """
        r = await self.session.get(
            f"https://iot.quasar.yandex.ru/m/user/devices/{device['id']}/configuration"
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp
        # device_id and platform
        device.update(resp["quasar_info"])

    async def load_scenarios(self):
        """Получает список сценариев, которые мы ранее создали."""
        r = await self.session.get(f"https://iot.quasar.yandex.ru/m/user/scenarios")
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
            f"https://iot.quasar.yandex.ru/m/v4/user/scenarios/{sid}/edit"
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

    async def add_scenario(self, device_id: str, hash: str) -> str:
        """Добавляет сценарий-пустышку."""
        payload = scenario_speaker_tts("ХА " + device_id, hash, device_id, "пустышка")
        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/v4/user/scenarios", json=payload
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp
        return resp["scenario_id"]

    async def send(self, device: dict, text: str, is_tts: bool = False):
        """Запускает сценарий на выполнение команды или TTS."""
        # skip send for yandex modules
        if "scenario_id" not in device:
            return
        _LOGGER.debug(f"{device['name']} => cloud | {text}")

        device_id = device["id"]
        name = "ХА " + device_id
        trigger = encode(device_id)
        payload = (
            scenario_speaker_tts(name, trigger, device_id, text)
            if is_tts
            else scenario_speaker_action(name, trigger, device_id, text)
        )

        sid = device["scenario_id"]

        r = await self.session.put(
            f"https://iot.quasar.yandex.ru/m/v4/user/scenarios/{sid}", json=payload
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/user/scenarios/{sid}/actions"
        )
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

    async def get_device_config(self, device: dict) -> (dict, str):
        did = device["id"]
        r = await self.session.get(
            f"https://iot.quasar.yandex.ru/m/v2/user/devices/{did}/configuration"
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp
        return resp["quasar_config"], resp["quasar_config_version"]

    async def set_device_config(self, device: dict, config: dict, version: str):
        _LOGGER.debug(f"Меняем конфиг станции: {config}")

        did = device["id"]
        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/v3/user/devices/{did}/configuration/quasar",
            json={"config": config, "version": version},
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

    async def get_device(self, device: dict):
        r = await self.session.get(
            f"https://iot.quasar.yandex.ru/m/user/{device['item_type']}s/{device['id']}"
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp
        return resp

    async def device_action(self, device: dict, instance: str, value):
        action = {"state": {"instance": instance, "value": value}}

        if instance in IOT_TYPES:
            action["type"] = IOT_TYPES[instance]
        elif instance.isdecimal():
            action["type"] = "devices.capabilities.custom.button"
        else:
            return

        r = await self.session.post(
            f"https://iot.quasar.yandex.ru/m/user/{device['item_type']}s/{device['id']}/actions",
            json={"actions": [action]},
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

        await asyncio.sleep(1)

        device = await self.get_device(device)
        self.dispatch_update(device["id"], device)

    async def device_actions(self, device: dict, **kwargs):
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
            f"https://iot.quasar.yandex.ru/m/user/{device['item_type']}s/{device['id']}/actions",
            json={"actions": actions},
        )
        resp = await r.json()
        assert resp["status"] == "ok", resp

        # update device state
        device = await self.get_device(device)
        self.dispatch_update(device["id"], device)

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
                    _ = asyncio.create_task(self.get_voice_trigger(1))

    async def devices_passive_update(self, *args):
        try:
            r = await self.session.get(
                f"https://iot.quasar.yandex.ru/m/v3/user/devices", timeout=15
            )
            resp = await r.json()
            assert resp["status"] == "ok", resp

            for house in resp["households"]:
                if "sharing_info" in house:
                    continue
                for device in house["all"]:
                    self.dispatch_update(device["id"], device)
        except Exception as e:
            _LOGGER.debug(f"Devices forceupdate problem: {repr(e)}")

    async def get_voice_trigger(self, retries: int = 0):
        try:
            # 1. Get all scenarios history
            r = await self.session.get(
                "https://iot.quasar.yandex.ru/m/user/scenarios/history"
            )
            raw = await r.json()

            # 2. Search latest scenario with voice trigger
            for scenario in raw["scenarios"]:
                if scenario["trigger_type"] == "scenario.trigger.voice":
                    break
            else:
                return

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
                f"https://iot.quasar.yandex.ru/m/v4/user/scenarios/launches/{scenario['id']}"
            )
            raw = await r.json()

            for step in raw["launch"]["steps"]:
                for item in step["parameters"]["items"]:
                    if item["type"] != "step.action.item.device":
                        continue
                    device = item["value"]
                    # 5. Check if speaker device
                    if "quasar_info" not in device:
                        continue
                    device["scenario_name"] = raw["launch"]["name"]
                    self.dispatch_update(device["id"], device)

        except Exception as e:
            _LOGGER.debug("Can't get voice scenario", exc_info=e)

    async def run_forever(self):
        while not self.session.closed:
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
                f"https://iot.quasar.yandex.ru/m/user/settings",
                json={kv["key"]: kv["values"][value]},
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

    async def get_alarms(self, device: dict):
        r = await self.session.post(
            "https://rpc.alice.yandex.ru/gproxy/get_alarms",
            json={"device_ids": [device["quasar_info"]["device_id"]]},
            headers=ALARM_HEADERS,
        )
        resp = await r.json()
        return resp["alarms"]

    async def create_alarm(self, device: dict, alarm: dict) -> bool:
        alarm["device_id"] = device["quasar_info"]["device_id"]
        resp = await self.session.post(
            "https://rpc.alice.yandex.ru/gproxy/create_alarm",
            json={"alarm": alarm, "device_type": device["type"]},
            headers=ALARM_HEADERS,
        )
        return resp.ok

    async def change_alarm(self, device: dict, alarm: dict) -> bool:
        alarm["device_id"] = device["quasar_info"]["device_id"]
        resp = await self.session.post(
            "https://rpc.alice.yandex.ru/gproxy/change_alarm",
            json={"alarm": alarm, "device_type": device["type"]},
            headers=ALARM_HEADERS,
        )
        return resp.ok

    async def cancel_alarms(self, device: dict, alarm_id: str) -> bool:
        resp = await self.session.post(
            "https://rpc.alice.yandex.ru/gproxy/cancel_alarms",
            json={
                "device_alarm_ids": [
                    {
                        "alarm_id": alarm_id,
                        "device_id": device["quasar_info"]["device_id"],
                    }
                ],
            },
            headers=ALARM_HEADERS,
        )
        return resp.ok


ALARM_HEADERS = {
    "accept": "application/json",
    "origin": "https://yandex.ru",
    "x-ya-app-type": "iot-app",
    "x-ya-application": '{"app_id":"unknown","uuid":"unknown","lang":"ru"}',
}


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
    "адаптивная громкость": {
        "key": "aliceAdaptiveVolume",  # /get_account_config
        "values": {
            "да": {"enabled": True},
            "нет": {"enabled": False},
        },
    },
    "кроссфейд": {
        "key": "audio_player",  # /get_account_config
        "values": {
            "да": {"crossfadeEnabled": True},
            "нет": {"crossfadeEnabled": False},
        },
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
