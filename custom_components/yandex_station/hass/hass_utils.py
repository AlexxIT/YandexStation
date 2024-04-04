import json
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_INCLUDE
from homeassistant.core import HomeAssistant

from ..core.const import DOMAIN, DATA_CONFIG
from ..core.yandex_quasar import YandexQuasar

INCLUDE_KEYS = ("id", "name", "type", "room_name", "skill_id")
INCLUDE_ALL_TYPES = (
    "devices.types.camera",
    "devices.types.cooking",
    "devices.types.cooking.coffee_maker",
    "devices.types.cooking.multicooker",
    "devices.types.dishwasher",
    "devices.types.iron",
    "devices.types.openable",
    "devices.types.openable.curtain",
    "devices.types.pet_drinking_fountain",
    "devices.types.pet_feeder",
    "devices.types.washing_machine",
)


def incluce_devices(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> list[tuple[YandexQuasar, dict, dict]]:
    quasar: YandexQuasar = hass.data[DOMAIN][config_entry.unique_id]
    config: dict = hass.data[DOMAIN][DATA_CONFIG]
    includes = config.get(CONF_INCLUDE, []) + config_entry.options.get(CONF_INCLUDE, [])

    devices = []

    for conf in includes:
        for device in quasar.devices:
            if isinstance(conf, str):
                if conf == device["name"] or conf == device["id"]:
                    conf = (
                        include_all_config(device)
                        if device["type"] in INCLUDE_ALL_TYPES
                        else {}
                    )
                    devices.append((quasar, device, conf))
                    break
            elif isinstance(conf, dict):
                if any(conf[k] == device.get(k) for k in INCLUDE_KEYS if k in conf):
                    devices.append((quasar, device, conf))
                    break

    return devices


def include_all_config(device: dict) -> dict:
    return {
        "capabilities": [
            i["parameters"].get("instance", "on") for i in device["capabilities"]
        ],
        "properties": [i["parameters"]["instance"] for i in device["properties"]],
    }


def load_fake_devies(hass: HomeAssistant, quasar: YandexQuasar):
    path = hass.config.path(DOMAIN + ".json")
    if os.path.isfile(path):
        with open(path, "rb") as f:
            quasar.devices += json.load(f)
