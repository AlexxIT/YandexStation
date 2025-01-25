import json
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_INCLUDE
from homeassistant.core import HomeAssistant

from ..climate import INCLUDE_TYPES as CLIMATE
from ..core.const import DATA_CONFIG, DOMAIN
from ..core.yandex_quasar import YandexQuasar
from ..cover import INCLUDE_TYPES as COVER
from ..humidifier import INCLUDE_TYPES as HUMIDIFIER
from ..light import INCLUDE_TYPES as LIGHT
from ..media_player import INCLUDE_TYPES as MEDIA_PLAYER
from ..vacuum import INCLUDE_TYPES as VACUUM
from ..water_heater import INCLUDE_TYPES as WATER_HEATER

INCLUDE_KEYS = ("id", "name", "type", "room_name", "skill_id", "house_name")

INCLUDE_TYPES_UNKNOWN = (
    "devices.types.camera",
    "devices.types.cooking",
    "devices.types.cooking.coffee_maker",
    "devices.types.cooking.multicooker",
    "devices.types.dishwasher",
    "devices.types.iron",
    "devices.types.openable",
    "devices.types.other",
    "devices.types.pet_drinking_fountain",
    "devices.types.pet_feeder",
    "devices.types.washing_machine",
)
INCLUDE_SKIP_INSTANCES = {
    CLIMATE: [
        "on",
        "thermostat",
        "program",
        "heat",
        "work_speed",
        "temperature",
        "humidity",
        "fan_speed",
    ],
    COVER: ["on", "open", "pause"],
    HUMIDIFIER: ["on", "fan_speed", "work_speed", "humidity"],
    LIGHT: ["on", "brightness", "color"],
    MEDIA_PLAYER: ["on", "pause", "volume", "mute", "channel", "input_source"],
    VACUUM: ["on", "pause", "work_speed", "battery_level"],
    WATER_HEATER: ["on", "tea_mode", "temperature"],
    INCLUDE_TYPES_UNKNOWN: [],
}


def incluce_devices(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> list[tuple[YandexQuasar, dict, dict]]:
    quasar: YandexQuasar = hass.data[DOMAIN][config_entry.unique_id]
    config: dict = hass.data[DOMAIN][DATA_CONFIG]
    # config_entry has more priority
    includes = config_entry.options.get(CONF_INCLUDE, []) + config.get(CONF_INCLUDE, [])

    devices = []

    # первый цикл по devices, второй по include, чтоб одинаковые include работали на
    # разные devices
    for device in quasar.devices:
        for conf in includes:
            if isinstance(conf, str):
                if conf == device["id"] or conf == device["name"]:
                    conf = build_include_config(device)
                    devices.append((quasar, device, conf))
                    break
            elif isinstance(conf, dict):
                if all(conf[k] == device.get(k) for k in INCLUDE_KEYS if k in conf):
                    devices.append((quasar, device, conf))
                    break

    return devices


def build_include_config(device: dict) -> dict:
    for include_types, include_skip in INCLUDE_SKIP_INSTANCES.items():
        if device["type"] in include_types:
            break
    else:
        return {}

    caps = [i["parameters"].get("instance", "on") for i in device["capabilities"]]
    props = [i["parameters"]["instance"] for i in device["properties"]]

    return {
        "capabilities": [i for i in caps if i not in include_skip],
        "properties": [i for i in props if i not in include_skip],
    }


async def load_fake_devies(hass: HomeAssistant, quasar: YandexQuasar):
    path = hass.config.path(DOMAIN + ".json")
    if not os.path.isfile(path):
        return

    def job():
        with open(path, "rb") as f:
            quasar.devices += json.load(f)

    await hass.async_add_executor_job(job)
