import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.light import ColorMode, LightEntityFeature
from homeassistant.exceptions import HomeAssistantError

from custom_components.yandex_station.light import YandexLight
from custom_components.yandex_station.core.yandex_quasar import YandexQuasar
from . import false, null, true, update_ha_state


def fix_hass_2024_12(state):
    attrs = dict(state.attributes)
    attrs.pop("rgb_color", None)
    attrs.pop("xy_color", None)

    # fix hass 2026.5
    attrs.pop("color_temp", None)
    attrs.pop("max_mireds", None)
    attrs.pop("min_mireds", None)

    # fix hass 2023.2
    attrs.setdefault("color_mode", None)
    if attrs["supported_features"] & LightEntityFeature.EFFECT:
        attrs.setdefault("effect", None)
    if ColorMode.COLOR_TEMP in attrs["supported_color_modes"]:
        attrs.setdefault("brightness", None)
        attrs.setdefault("color_temp_kelvin", None)
    if ColorMode.HS in attrs["supported_color_modes"]:
        attrs.setdefault("hs_color", None)

    state.attributes = attrs


def test_light_white():
    device = {
        "id": "xxx",
        "name": "Детская Свет",
        "type": "devices.types.light",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.light.svg/orig",
        "capabilities": [
            {
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.color_setting",
                "state": {
                    "instance": "color",
                    "value": {
                        "id": "white",
                        "name": "Белый",
                        "type": "white",
                        "value": {"h": 33, "s": 28, "v": 100},
                    },
                },
                "parameters": {
                    "instance": "color",
                    "name": "цвет",
                    "palette": [
                        {
                            "id": "soft_white",
                            "name": "Мягкий белый",
                            "type": "white",
                            "value": {"h": 32, "s": 67, "v": 100},
                        },
                        {
                            "id": "warm_white",
                            "name": "Теплый белый",
                            "type": "white",
                            "value": {"h": 33, "s": 49, "v": 100},
                        },
                        {
                            "id": "white",
                            "name": "Белый",
                            "type": "white",
                            "value": {"h": 33, "s": 28, "v": 100},
                        },
                        {
                            "id": "daylight",
                            "name": "Дневной белый",
                            "type": "white",
                            "value": {"h": 36, "s": 35, "v": 97},
                        },
                        {
                            "id": "cold_white",
                            "name": "Холодный белый",
                            "type": "white",
                            "value": {"h": 222, "s": 4, "v": 98},
                        },
                    ],
                    "custom_palette": null,
                    "scenes": [],
                    "custom_scenes": null,
                    "available_custom_settings": false,
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "brightness", "value": 100},
                "parameters": {
                    "instance": "brightness",
                    "name": "яркость",
                    "unit": "unit.percent",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 1, "max": 100, "precision": 1},
                },
            },
        ],
        "properties": [],
        "item_type": "device",
        "skill_id": "xxx",
        "room_name": "Детская",
        "state": "online",
        "created": "2022-08-13T12:34:44Z",
        "parameters": {
            "device_info": {
                "manufacturer": "yeelink",
                "model": "yeelink.light.ceiling6",
                "sw_version": "1.5.9_0017",
            }
        },
    }

    state = update_ha_state(YandexLight, device)
    fix_hass_2024_12(state)
    assert state.state == "on"
    assert state.attributes == {
        "brightness": 255,
        "color_mode": ColorMode.HS,
        "effect": "Белый",
        "effect_list": [
            "Мягкий белый",
            "Теплый белый",
            "Белый",
            "Дневной белый",
            "Холодный белый",
        ],
        "friendly_name": "Детская Свет",
        "hs_color": (33, 28),
        # "rgb_color": (255, 222, 183),
        "supported_color_modes": [ColorMode.HS],
        "supported_features": LightEntityFeature.EFFECT,
        # "xy_color": (0.394, 0.366),
    }


def test_light_multicolor():
    device = {
        "id": "xxx",
        "name": "Ночник",
        "type": "devices.types.light",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.light.svg/orig",
        "capabilities": [
            {
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.color_setting",
                "state": {
                    "instance": "color",
                    "value": {
                        "id": "warm_white",
                        "name": "Теплый белый",
                        "type": "white",
                        "value": {"h": 33, "s": 49, "v": 100},
                    },
                },
                "parameters": {
                    "instance": "color",
                    "name": "цвет",
                    "palette": [
                        {
                            "id": "soft_white",
                            "name": "Мягкий белый",
                            "type": "white",
                            "value": {"h": 32, "s": 67, "v": 100},
                        },
                        {
                            "id": "warm_white",
                            "name": "Теплый белый",
                            "type": "white",
                            "value": {"h": 33, "s": 49, "v": 100},
                        },
                        {
                            "id": "white",
                            "name": "Белый",
                            "type": "white",
                            "value": {"h": 33, "s": 28, "v": 100},
                        },
                        {
                            "id": "daylight",
                            "name": "Дневной белый",
                            "type": "white",
                            "value": {"h": 36, "s": 35, "v": 97},
                        },
                        {
                            "id": "cold_white",
                            "name": "Холодный белый",
                            "type": "white",
                            "value": {"h": 222, "s": 4, "v": 98},
                        },
                        {
                            "id": "red",
                            "name": "Красный",
                            "type": "multicolor",
                            "value": {"h": 0, "s": 65, "v": 100},
                        },
                        {
                            "id": "coral",
                            "name": "Коралловый",
                            "type": "multicolor",
                            "value": {"h": 8, "s": 55, "v": 98},
                        },
                        {
                            "id": "orange",
                            "name": "Оранжевый",
                            "type": "multicolor",
                            "value": {"h": 25, "s": 70, "v": 100},
                        },
                        {
                            "id": "yellow",
                            "name": "Желтый",
                            "type": "multicolor",
                            "value": {"h": 40, "s": 70, "v": 100},
                        },
                        {
                            "id": "lime",
                            "name": "Салатовый",
                            "type": "multicolor",
                            "value": {"h": 73, "s": 96, "v": 100},
                        },
                        {
                            "id": "green",
                            "name": "Зеленый",
                            "type": "multicolor",
                            "value": {"h": 120, "s": 55, "v": 90},
                        },
                        {
                            "id": "emerald",
                            "name": "Изумрудный",
                            "type": "multicolor",
                            "value": {"h": 160, "s": 80, "v": 90},
                        },
                        {
                            "id": "turquoise",
                            "name": "Бирюзовый",
                            "type": "multicolor",
                            "value": {"h": 180, "s": 80, "v": 90},
                        },
                        {
                            "id": "cyan",
                            "name": "Голубой",
                            "type": "multicolor",
                            "value": {"h": 190, "s": 60, "v": 100},
                        },
                        {
                            "id": "blue",
                            "name": "Синий",
                            "type": "multicolor",
                            "value": {"h": 225, "s": 55, "v": 90},
                        },
                        {
                            "id": "moonlight",
                            "name": "Лунный",
                            "type": "multicolor",
                            "value": {"h": 231, "s": 10, "v": 100},
                        },
                        {
                            "id": "lavender",
                            "name": "Сиреневый",
                            "type": "multicolor",
                            "value": {"h": 255, "s": 55, "v": 90},
                        },
                        {
                            "id": "violet",
                            "name": "Фиолетовый",
                            "type": "multicolor",
                            "value": {"h": 270, "s": 55, "v": 90},
                        },
                        {
                            "id": "purple",
                            "name": "Пурпурный",
                            "type": "multicolor",
                            "value": {"h": 300, "s": 70, "v": 90},
                        },
                        {
                            "id": "orchid",
                            "name": "Розовый",
                            "type": "multicolor",
                            "value": {"h": 305, "s": 50, "v": 90},
                        },
                        {
                            "id": "raspberry",
                            "name": "Малиновый",
                            "type": "multicolor",
                            "value": {"h": 345, "s": 70, "v": 90},
                        },
                        {
                            "id": "mauve",
                            "name": "Лиловый",
                            "type": "multicolor",
                            "value": {"h": 340, "s": 45, "v": 90},
                        },
                    ],
                    "custom_palette": null,
                    "scenes": [],
                    "custom_scenes": null,
                    "available_custom_settings": false,
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "brightness", "value": 1},
                "parameters": {
                    "instance": "brightness",
                    "name": "яркость",
                    "unit": "unit.percent",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 1, "max": 100, "precision": 1},
                },
            },
        ],
        "properties": [],
        "item_type": "device",
        "skill_id": "xxx",
        "room_name": "Зал",
        "state": "online",
        "created": "2022-08-13T12:34:44Z",
        "parameters": {
            "device_info": {
                "manufacturer": "yeelink",
                "model": "yeelink.light.bslamp2",
                "sw_version": "2.0.6_0033",
            }
        },
    }

    state = update_ha_state(YandexLight, device)
    fix_hass_2024_12(state)
    assert state.state == "on"
    assert state.attributes == {
        "brightness": 1,
        "color_mode": ColorMode.HS,
        "effect": "Теплый белый",
        "effect_list": [
            "Мягкий белый",
            "Теплый белый",
            "Белый",
            "Дневной белый",
            "Холодный белый",
            "Красный",
            "Коралловый",
            "Оранжевый",
            "Желтый",
            "Салатовый",
            "Зеленый",
            "Изумрудный",
            "Бирюзовый",
            "Голубой",
            "Синий",
            "Лунный",
            "Сиреневый",
            "Фиолетовый",
            "Пурпурный",
            "Розовый",
            "Малиновый",
            "Лиловый",
        ],
        "friendly_name": "Ночник",
        "hs_color": (33, 49),
        # "rgb_color": (255, 198, 130),
        "supported_color_modes": [ColorMode.HS],
        "supported_features": LightEntityFeature.EFFECT,
        # "xy_color": (0.458, 0.391),
    }


def test_scenes():
    device = {
        "id": "xxx",
        "name": "Кровать",
        "type": "devices.types.switch",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.switch.svg/orig",
        "capabilities": [
            {
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.color_setting",
                "state": {
                    "instance": "scene",
                    "value": {"id": "movie", "name": "Кино"},
                },
                "parameters": {
                    "instance": "color",
                    "name": "цвет",
                    "palette": null,
                    "custom_palette": null,
                    "scenes": [
                        {"id": "movie", "name": "Кино"},
                        {"id": "night", "name": "Ночь"},
                        {"id": "rest", "name": "Отдых"},
                        {"id": "reading", "name": "Чтение"},
                    ],
                    "custom_scenes": null,
                    "available_custom_settings": false,
                },
            },
        ],
        "properties": [],
        "item_type": "device",
        "skill_id": "xxx",
        "room_name": "Спальня",
        "state": "online",
        "created": "2023-10-01T15:27:56Z",
        "parameters": {
            "device_info": {
                "manufacturer": "Ergomotion",
                "model": "light.xxx_scene",
            }
        },
    }

    state = update_ha_state(YandexLight, device)
    assert state.state == "on"
    assert state.attributes == {
        "color_mode": ColorMode.UNKNOWN,
        "effect": "Кино",
        "effect_list": ["Кино", "Ночь", "Отдых", "Чтение"],
        "friendly_name": "Кровать",
        "supported_color_modes": [ColorMode.ONOFF],
        "supported_features": LightEntityFeature.EFFECT,
    }


def test_issue465():
    device = {
        "id": "xxx",
        "name": "Лампа",
        "type": "devices.types.light",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.light.svg/orig",
        "capabilities": [
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.color_setting",
                "state": {
                    "instance": "color",
                    "value": {"id": "", "name": "", "type": "white", "value": 3012},
                },
                "parameters": {
                    "instance": "color",
                    "name": "цвет",
                    "palette": [
                        {
                            "id": "soft_white",
                            "name": "Мягкий белый",
                            "type": "white",
                            "value": {"h": 32, "s": 67, "v": 100},
                        },
                        {
                            "id": "warm_white",
                            "name": "Теплый белый",
                            "type": "white",
                            "value": {"h": 33, "s": 49, "v": 100},
                        },
                        {
                            "id": "white",
                            "name": "Белый",
                            "type": "white",
                            "value": {"h": 33, "s": 28, "v": 100},
                        },
                        {
                            "id": "daylight",
                            "name": "Дневной белый",
                            "type": "white",
                            "value": {"h": 36, "s": 35, "v": 97},
                        },
                        {
                            "id": "cold_white",
                            "name": "Холодный белый",
                            "type": "white",
                            "value": {"h": 222, "s": 4, "v": 98},
                        },
                    ],
                    "custom_palette": null,
                    "scenes": [],
                    "custom_scenes": null,
                    "available_custom_settings": false,
                    "temperature_k": {"min": 2000, "max": 6500},
                },
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "brightness", "value": 3},
                "parameters": {
                    "instance": "brightness",
                    "name": "яркость",
                    "unit": "unit.percent",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 1, "max": 100, "precision": 1},
                },
            },
        ],
        "properties": [],
        "item_type": "device",
        "skill_id": "c927bb15-5ecb-472a-8895-c3740602d36a",
        "room_name": "Коридор",
        "state": "online",
        "created": "2021-04-18T10:24:26Z",
        "parameters": {
            "device_info": {
                "manufacturer": "Aqara",
                "model": "ZNLDP12LM",
                "hw_version": "1.0",
                "sw_version": "0.0.0_0034",
            }
        },
    }

    state = update_ha_state(YandexLight, device)
    fix_hass_2024_12(state)
    assert state.state == "on"
    assert state.attributes == {
        "brightness": 6,
        "color_mode": ColorMode.COLOR_TEMP,
        # "color_temp": 332,
        "color_temp_kelvin": 3012,
        "effect": None,
        "effect_list": [
            "Мягкий белый",
            "Теплый белый",
            "Белый",
            "Дневной белый",
            "Холодный белый",
        ],
        "friendly_name": "Лампа",
        "hs_color": (27.806, 56.57),
        "max_color_temp_kelvin": 6500,
        # "max_mireds": 500,
        "min_color_temp_kelvin": 2000,
        # "min_mireds": 153,
        # "rgb_color": (255, 177, 110),
        "supported_color_modes": [ColorMode.COLOR_TEMP, ColorMode.HS],
        "supported_features": LightEntityFeature.EFFECT,
        # "xy_color": (0.496, 0.383),
    }


def test_issue711():
    device = {
        "id": "xxx",
        "name": "Свет на крыльце",
        "type": "devices.types.light",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.light.svg/orig",
        "capabilities": [
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state_changed_at": 1761939645.3040287,
                "last_updated": 1761977954.1980345,
                "parameters": {"split": false},
                "state": {"instance": "on", "value": false},
            },
            {
                "reportable": true,
                "retrievable": false,
                "type": "devices.capabilities.zigbee_node",
                "state_changed_at": 1761978012.2432792,
                "last_updated": 1761978012.2432792,
                "parameters": {"type": "router"},
                "state": {
                    "value": {
                        "signal_quality": {"status": "ok", "lqi": 75, "rssi": -74}
                    }
                },
            },
        ],
        "properties": [
            {
                "type": "devices.properties.float",
                "retrievable": false,
                "reportable": true,
                "parameters": {
                    "instance": "power",
                    "name": "потребляемая мощность",
                    "unit": "unit.watt",
                    "range": {"min": 0, "max": 3500, "precision": 0.1},
                },
                "state": {"percent": null, "status": null, "value": 0},
                "state_changed_at": "2025-10-31T19:40:46Z",
                "last_updated": "2025-11-01T05:38:23Z",
            }
        ],
        "skill_id": "YANDEX_IO",
        "item_type": "device",
        "groups": [],
    }

    state = update_ha_state(YandexLight, device)
    fix_hass_2024_12(state)
    assert state.state == "off"
    assert state.attributes == {
        "color_mode": None,
        "friendly_name": "Свет на крыльце",
        "supported_color_modes": [ColorMode.ONOFF],
        "supported_features": 0,
    }


def test_strip():
    device = {
        "id": "xxx",
        "external_id": "iot_matter_XXXXXXXXXXXX_1",
        "name": "Лента",
        "type": "devices.types.light.strip",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.light.strip.svg/orig",
        "capabilities": [
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
                "can_be_deferred": true,
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.color_setting",
                "state": {
                    "instance": "scene",
                    "value": {"id": "romance", "steps": null},
                },
                "parameters": {
                    "instance": "color",
                    "name": "цвет",
                    "palette": [
                        {
                            "id": "soft_white",
                            "name": "Мягкий белый",
                            "type": "white",
                            "value": {"h": 32, "s": 67, "v": 100},
                        },
                        {
                            "id": "warm_white",
                            "name": "Теплый белый",
                            "type": "white",
                            "value": {"h": 33, "s": 49, "v": 100},
                        },
                        {
                            "id": "white",
                            "name": "Белый",
                            "type": "white",
                            "value": {"h": 33, "s": 28, "v": 100},
                        },
                        {
                            "id": "daylight",
                            "name": "Дневной белый",
                            "type": "white",
                            "value": {"h": 36, "s": 35, "v": 97},
                        },
                        {
                            "id": "cold_white",
                            "name": "Холодный белый",
                            "type": "white",
                            "value": {"h": 222, "s": 4, "v": 98},
                        },
                        {
                            "id": "red",
                            "name": "Красный",
                            "type": "multicolor",
                            "value": {"h": 0, "s": 65, "v": 100},
                        },
                        {
                            "id": "coral",
                            "name": "Коралловый",
                            "type": "multicolor",
                            "value": {"h": 8, "s": 55, "v": 98},
                        },
                        {
                            "id": "orange",
                            "name": "Оранжевый",
                            "type": "multicolor",
                            "value": {"h": 25, "s": 70, "v": 100},
                        },
                        {
                            "id": "yellow",
                            "name": "Желтый",
                            "type": "multicolor",
                            "value": {"h": 40, "s": 70, "v": 100},
                        },
                        {
                            "id": "lime",
                            "name": "Салатовый",
                            "type": "multicolor",
                            "value": {"h": 73, "s": 96, "v": 100},
                        },
                        {
                            "id": "green",
                            "name": "Зеленый",
                            "type": "multicolor",
                            "value": {"h": 120, "s": 55, "v": 90},
                        },
                        {
                            "id": "emerald",
                            "name": "Изумрудный",
                            "type": "multicolor",
                            "value": {"h": 160, "s": 80, "v": 90},
                        },
                        {
                            "id": "turquoise",
                            "name": "Бирюзовый",
                            "type": "multicolor",
                            "value": {"h": 180, "s": 80, "v": 90},
                        },
                        {
                            "id": "cyan",
                            "name": "Голубой",
                            "type": "multicolor",
                            "value": {"h": 190, "s": 60, "v": 100},
                        },
                        {
                            "id": "blue",
                            "name": "Синий",
                            "type": "multicolor",
                            "value": {"h": 225, "s": 55, "v": 90},
                        },
                        {
                            "id": "moonlight",
                            "name": "Лунный",
                            "type": "multicolor",
                            "value": {"h": 231, "s": 10, "v": 100},
                        },
                        {
                            "id": "lavender",
                            "name": "Сиреневый",
                            "type": "multicolor",
                            "value": {"h": 255, "s": 55, "v": 90},
                        },
                        {
                            "id": "violet",
                            "name": "Фиолетовый",
                            "type": "multicolor",
                            "value": {"h": 270, "s": 55, "v": 90},
                        },
                        {
                            "id": "purple",
                            "name": "Пурпурный",
                            "type": "multicolor",
                            "value": {"h": 300, "s": 70, "v": 90},
                        },
                        {
                            "id": "orchid",
                            "name": "Розовый",
                            "type": "multicolor",
                            "value": {"h": 305, "s": 50, "v": 90},
                        },
                        {
                            "id": "raspberry",
                            "name": "Малиновый",
                            "type": "multicolor",
                            "value": {"h": 345, "s": 70, "v": 90},
                        },
                        {
                            "id": "mauve",
                            "name": "Лиловый",
                            "type": "multicolor",
                            "value": {"h": 340, "s": 45, "v": 90},
                        },
                    ],
                    "custom_palette": null,
                    "scenes": [
                        {"id": "sunrise", "name": "Рассвет"},
                        {"id": "sunset", "name": "Закат"},
                        {"id": "circadian", "name": "Циркадный"},
                        {"id": "party", "name": "Вечеринка"},
                        {"id": "gaming", "name": "Игра"},
                        {"id": "night", "name": "Вечерний"},
                        {"id": "romance", "name": "Романтика"},
                        {"id": "candle", "name": "Свеча"},
                        {"id": "northern", "name": "Северное сияние"},
                        {"id": "reading", "name": "Чтение"},
                    ],
                    "custom_scenes": null,
                    "custom_scenes_available": true,
                    "color_model": "hsv",
                    "temperature_k": {"min": 2700, "max": 6500},
                },
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "brightness", "value": 99},
                "parameters": {
                    "instance": "brightness",
                    "name": "яркость",
                    "unit": "unit.percent",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 1, "max": 100, "precision": 1},
                },
            },
        ],
        "properties": [],
        "item_type": "device",
        "skill_id": "YANDEX_IO",
        "room_name": "Лоджия",
        "status_info": {
            "status": "online",
            "updated": 1765305703.998412,
            "changed": 1764860708.344743,
        },
        "state": "online",
        "render_info": {"icon": {"id": "yandex.light.unicorn", "color": "white"}},
        "created": "2025-10-13T14:20:54Z",
        "parameters": {
            "device_info": {
                "manufacturer": "Yandex",
                "model": "YNDX-00544",
                "hw_version": "0",
                "sw_version": "20",
                "setup_code": "XXX",
                "serial_number": "XXX",
                "vendor_id": 5130,
                "product_id": 544,
            },
            "ota_update": {"status": "success", "progress": 100, "version": 0},
        },
    }

    state = update_ha_state(YandexLight, device)
    fix_hass_2024_12(state)
    assert state.state == "on"
    assert state.attributes == {
        "brightness": None,
        "color_mode": ColorMode.UNKNOWN,
        # "color_temp": None,
        "color_temp_kelvin": None,
        "effect": "Романтика",
        "effect_list": [
            "Мягкий белый",
            "Теплый белый",
            "Белый",
            "Дневной белый",
            "Холодный белый",
            "Красный",
            "Коралловый",
            "Оранжевый",
            "Желтый",
            "Салатовый",
            "Зеленый",
            "Изумрудный",
            "Бирюзовый",
            "Голубой",
            "Синий",
            "Лунный",
            "Сиреневый",
            "Фиолетовый",
            "Пурпурный",
            "Розовый",
            "Малиновый",
            "Лиловый",
            "Рассвет",
            "Закат",
            "Циркадный",
            "Вечеринка",
            "Игра",
            "Вечерний",
            "Романтика",
            "Свеча",
            "Северное сияние",
            "Чтение",
        ],
        "friendly_name": "Лента",
        "hs_color": None,
        "max_color_temp_kelvin": 6500,
        # "max_mireds": 370,
        "min_color_temp_kelvin": 2700,
        # "min_mireds": 153,
        # "rgb_color": None,
        "supported_color_modes": [ColorMode.COLOR_TEMP, ColorMode.HS],
        "supported_features": LightEntityFeature.EFFECT,
        # "xy_color": None,
    }


def station3_device() -> dict:
    # Yandex Station 3 backlight (trimmed palette and scenes)
    return {
        "id": "xxx",
        "name": "Яндекс Станция 3",
        "type": "devices.types.smart_speaker.yandex.station.orion",
        "capabilities": [
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.color_setting",
                "state": {
                    "instance": "scene",
                    "value": {"id": "inactive", "name": "Неактивный"},
                },
                "parameters": {
                    "instance": "color",
                    "name": "цвет",
                    "palette": [
                        {
                            "id": "red",
                            "name": "Красный",
                            "type": "multicolor",
                            "value": {"h": 0, "s": 65, "v": 100},
                        },
                        {
                            "id": "blue",
                            "name": "Синий",
                            "type": "multicolor",
                            "value": {"h": 225, "s": 55, "v": 90},
                        },
                    ],
                    "custom_palette": null,
                    "scenes": [
                        {"id": "night", "name": "Ночь"},
                        {"id": "candle", "name": "Свеча"},
                        {"id": "polar_lights", "name": "Северное Сияние"},
                        {"id": "sunset", "name": "Закат"},
                        {"id": "color_music", "name": "Светомузыка"},
                        {"id": "stroboscope", "name": "Стробоскоп"},
                    ],
                    "custom_scenes": null,
                    "available_custom_settings": false,
                    "temperature_k": {"min": 1000, "max": 9000},
                },
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.color_animation",
                "state": {
                    "instance": "color_animation",
                    "value": {
                        "current_animation_type": "scene",
                        "animations": {
                            "color": {
                                "variant": "orchid",
                                "internal_state": {
                                    "instance": "hsv",
                                    "value": {"h": 325, "s": 96, "v": 100},
                                },
                            },
                            "scene": {
                                "variant": "candle",
                                "variants": [
                                    {"id": "night", "options": []},
                                    {
                                        "id": "candle",
                                        "options": [
                                            {"instance": "sound", "enabled": false}
                                        ],
                                    },
                                    {"id": "polar_lights", "options": []},
                                ],
                            },
                            "color_music": {
                                "variant": "color_music",
                                "settings": [],
                                "variants": [
                                    {
                                        "id": "color_music",
                                        "options": [
                                            {"instance": "autoplay", "enabled": true}
                                        ],
                                    },
                                    {
                                        "id": "stroboscope",
                                        "options": [
                                            {
                                                "instance": "palette",
                                                "color_id": "",
                                                "color_model": "",
                                                "value": null,
                                            }
                                        ],
                                    },
                                ],
                            },
                        },
                    },
                },
                "parameters": {
                    "instance": "color_animation",
                    "animations": {
                        "scene": {
                            "variants": [
                                {"id": "night"}, {"id": "candle"},
                                {"id": "polar_lights"}, {"id": "sunset"},
                            ],
                        },
                        "color_music": {
                            "variants": [
                                {"id": "stroboscope", "options": [{"instance": "palette"}]},
                                {
                                    "id": "color_music",
                                    "options": [{"instance": "autoplay", "type": "autoplay"}],
                                },
                            ],
                        },
                    },
                },
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "brightness", "value": 33},
                "parameters": {
                    "instance": "brightness",
                    "name": "яркость",
                    "unit": "unit.percent",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 1, "max": 100, "precision": 1},
                },
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.toggle",
                "state": {"instance": "backlight", "value": true},
                "parameters": {"instance": "backlight", "name": "подсветка"},
            },
        ],
        "properties": [],
        "item_type": "device",
        "quasar_info": {"device_id": "xxx", "platform": "orion"},
        "state": "online",
    }


def test_station3_backlight():
    state = update_ha_state(YandexLight, station3_device())
    assert state.state == "on"
    assert state.attributes["brightness"] == 83
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes["effect"] == "Свеча"
    assert state.attributes["effect_list"] == [
        "Красный",
        "Синий",
        "Ночь",
        "Свеча",
        "Северное Сияние",
        "Закат",
        "Светомузыка",
        "Стробоскоп",
    ]
    assert set(state.attributes["supported_color_modes"]) == {
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    }
    assert state.attributes["supported_features"] == LightEntityFeature.EFFECT
    assert state.attributes["min_color_temp_kelvin"] == 1000
    assert state.attributes["max_color_temp_kelvin"] == 9000


def test_station3_actions():
    import asyncio

    from . import FakeQuasar

    class ActionsQuasar(FakeQuasar):
        def __init__(self, data: dict):
            super().__init__(data)
            self.actions = []

        async def device_actions(self, device: dict, **kwargs):
            self.actions.append(kwargs)

        async def device_action(self, device: dict, instance: str, value, relative=False):
            self.actions.append({instance: value})

    device = station3_device()
    quasar = ActionsQuasar(device)
    entity = YandexLight(quasar, device)
    assert entity.animation

    # scene via color_animation (same payload as Yandex app)
    asyncio.run(entity.async_turn_on(effect="Северное Сияние"))
    assert quasar.actions == [
        {
            "color_animation": {
                "current_animation_type": "scene",
                "animations": {
                    "scene": {
                        "variant": "polar_lights",
                        "variants": [{"id": "polar_lights", "options": []}],
                    }
                },
            }
        }
    ]

    # palette color via color_animation
    quasar.actions.clear()
    asyncio.run(entity.async_turn_on(effect="Синий"))
    assert quasar.actions == [
        {
            "color_animation": {
                "current_animation_type": "color",
                "animations": {"color": {"variant": "blue"}},
            }
        }
    ]

    # backlight is off: turn it on together with the scene, keep scene options
    quasar.actions.clear()
    entity.internal_update({"backlight": false}, {})
    asyncio.run(entity.async_turn_on(effect="Свеча"))
    assert quasar.actions == [
        {
            "backlight": true,
            "color_animation": {
                "current_animation_type": "scene",
                "animations": {
                    "scene": {
                        "variant": "candle",
                        "variants": [
                            {
                                "id": "candle",
                                "options": [{"instance": "sound", "enabled": false}],
                            }
                        ],
                    }
                },
            },
        }
    ]

    quasar.actions.clear()
    asyncio.run(entity.async_turn_off())
    assert quasar.actions == [{"backlight": false}]

    # dynamic scene: absent from variants, state reports variants as null
    entity.internal_update(
        {
            "backlight": true,
            "color_animation": {
                "current_animation_type": "scene",
                "animations": {"scene": {"variant": "sunset", "variants": null}},
            },
        },
        {},
    )
    assert entity.effect == "Закат"
    quasar.actions.clear()
    asyncio.run(entity.async_turn_on(effect="Закат"))
    assert quasar.actions == [
        {
            "color_animation": {
                "current_animation_type": "scene",
                "animations": {
                    "scene": {
                        "variant": "sunset",
                        "variants": [{"id": "sunset", "options": []}],
                    }
                },
            }
        }
    ]


def test_station3_music_actions_preserve_options_and_reported_state():
    device = station3_device()
    device["capabilities"][3]["state"]["value"] = False
    original = deepcopy(device)
    session = AsyncMock()
    session.post.return_value.json.return_value = {"status": "ok"}
    reported = deepcopy(device)
    reported["capabilities"][3]["state"]["value"] = True
    reported["capabilities"][2]["state"]["value"] = 50
    animation = reported["capabilities"][1]["state"]["value"]
    animation["current_animation_type"] = "color_music"
    session.get.return_value.json.return_value = {"status": "ok", **reported}
    entity = YandexLight(YandexQuasar(session), device)

    asyncio.run(entity.async_turn_on(effect="Светомузыка", brightness=128))

    session.post.assert_awaited_once_with(
        "https://iot.quasar.yandex.ru/m/user/devices/xxx/actions",
        json={
            "actions": [
                {
                    "type": "devices.capabilities.toggle",
                    "state": {"instance": "backlight", "value": True},
                },
                {
                    "type": "devices.capabilities.range",
                    "state": {"instance": "brightness", "value": 50},
                },
                {
                    "type": "devices.capabilities.color_animation",
                    "state": {
                        "instance": "color_animation",
                        "value": {
                            "current_animation_type": "color_music",
                            "animations": {
                                "color_music": {
                                    "variant": "color_music",
                                    "variants": [{
                                        "id": "color_music",
                                        "options": [{"instance": "autoplay", "enabled": True}],
                                    }],
                                },
                            },
                        },
                    },
                },
            ],
        },
    )
    assert entity.is_on
    assert entity.effect == "Светомузыка"
    assert entity.brightness == 127  # Reported 50% in the device's 1..100 range.
    assert device == original

    session.post.reset_mock()
    animation["animations"]["color_music"]["variant"] = "stroboscope"
    asyncio.run(entity.async_turn_on(effect="Стробоскоп"))
    assert session.post.await_args.args[0].endswith("/actions")
    actions = session.post.await_args.kwargs["json"]["actions"]
    assert actions == [{
        "type": "devices.capabilities.color_animation",
        "state": {
            "instance": "color_animation",
            "value": {
                "current_animation_type": "color_music",
                "animations": {
                    "color_music": {
                        "variant": "stroboscope",
                        "variants": [{
                            "id": "stroboscope",
                            "options": [{
                                "instance": "palette", "color_id": "",
                                "color_model": "", "value": None,
                            }],
                        }],
                    },
                },
            },
        },
    }]
    assert entity.effect == "Стробоскоп"
    assert device == original


def test_station3_music_without_saved_options_does_not_reset_them():
    device = station3_device()
    device["capabilities"][1]["state"]["value"] = None
    session = AsyncMock()
    session.post.return_value.json.return_value = {"status": "ok"}
    session.get.return_value.json.return_value = {"status": "ok", **device}
    entity = YandexLight(YandexQuasar(session), device)

    asyncio.run(entity.async_turn_on(effect="Светомузыка"))

    session.post.assert_awaited_once_with(
        "https://iot.quasar.yandex.ru/m/user/devices/xxx/actions",
        json={"actions": [{
            "type": "devices.capabilities.color_animation",
            "state": {
                "instance": "color_animation",
                "value": {
                    "current_animation_type": "color_music",
                    "animations": {"color_music": {"variant": "color_music"}},
                },
            },
        }]},
    )
    assert entity.effect != "Светомузыка"  # No optimistic success without a reported state.


def ambi_device() -> dict:
    return {
        "id": "synthetic-ambi",
        "name": "Ambi Lamp",
        "type": "devices.types.light.lamp",
        "item_type": "device",
        "state": "online",
        "capabilities": [
            {
                "type": "devices.capabilities.on_off",
                "retrievable": True,
                "parameters": {"split": False},
                "state": {"instance": "on", "value": True},
            },
            {
                "type": "devices.capabilities.range",
                "retrievable": True,
                "parameters": {
                    "instance": "brightness",
                    "range": {"min": 1, "max": 100},
                },
                "state": {"instance": "brightness", "value": 50},
            },
            {
                "type": "devices.capabilities.color_setting",
                "retrievable": True,
                "parameters": {
                    "instance": "color",
                    "palette": [
                        {
                            "id": "blue",
                            "name": "Синий",
                            "value": {"h": 225, "s": 55, "v": 90},
                        }
                    ],
                    "scenes": [
                        {"id": "night", "name": "Ночь"},
                        {"id": "sunset", "name": "Закат"},
                    ],
                    "temperature_k": {"min": 2700, "max": 6500},
                },
                "state": {"instance": "color", "value": {"id": "inactive"}},
            },
            {
                "type": "devices.capabilities.color_animation",
                "retrievable": True,
                "parameters": {
                    "instance": "color_animation",
                    "animations": {
                        "color_music": {
                            "variants": [
                                {"id": "equalizer", "options": []},
                                {"id": "party", "options": []},
                                {"id": "gaming", "options": []},
                            ],
                            "settings": [{"type": "autorun"}, {"type": "autoplay"}],
                        }
                    },
                },
                "state": {
                    "instance": "color_animation",
                    "value": {
                        "current_animation_type": "color_music",
                        "animations": {
                            "color_music": {
                                "variant": "party",
                                "settings": [
                                    {"instance": "autorun", "enabled": False},
                                    {"instance": "autoplay", "enabled": True},
                                ],
                            }
                        },
                    },
                },
            },
        ],
        "properties": [],
    }


def test_ambi_color_music_state():
    state = update_ha_state(YandexLight, ambi_device())
    assert state.attributes["effect"] == "Вечеринка"
    assert state.attributes["effect_list"] == [
        "Синий",
        "Ночь",
        "Закат",
        "Эквалайзер",
        "Вечеринка",
        "Игра",
    ]
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("color_temp_kelvin") is None


def test_ambi_select_music_without_changing_settings():
    device = ambi_device()
    original = deepcopy(device)
    session = AsyncMock()
    session.post.return_value.json.return_value = {
        "operations": [{"result": {"status": "DONE"}}]
    }
    session.get.return_value.json.return_value = {"status": "ok", **device}
    entity = YandexLight(YandexQuasar(session), device)

    asyncio.run(entity.async_turn_on(effect="Эквалайзер"))

    # Official IoT client: set_animation is separate from type settings.
    session.post.assert_awaited_once_with(
        "https://iot.quasar.yandex.ru/m/user/devices/synthetic-ambi/operations",
        json={
            "operations": [
                {
                    "capability_type": "devices.capabilities.color_animation",
                    "capability_instance": "color_animation",
                    "operation_type": "capabilities.color_animation.operations.set_animation",
                    "payload": {
                        "animation_type": "color_music",
                        "animation": {"id": "equalizer"},
                    },
                }
            ]
        },
    )
    assert device == original
    # A command does not replace the state returned by Quasar optimistically.
    assert entity.effect == "Вечеринка"


def test_music_effect_identity_and_partial_updates():
    device = ambi_device()
    color = device["capabilities"][2]
    animation = device["capabilities"][3]
    color["parameters"]["scenes"].append({"id": "party", "name": "Вечеринка"})
    animation["parameters"]["animations"]["color_music"]["variants"].append(
        {"id": "future_music", "options": []}
    )
    session = AsyncMock()
    session.post.return_value.json.return_value = {"status": "ok"}
    session.get.return_value.json.return_value = {"status": "ok", **device}
    quasar = YandexQuasar(session)
    entity = YandexLight(quasar, device)
    assert entity.effect == "Вечеринка (цветомузыка)"
    assert entity.effect_list == [
        "Синий", "Ночь", "Закат", "Вечеринка",
        "Эквалайзер", "Вечеринка (цветомузыка)", "Игра", "future_music",
    ]
    asyncio.run(entity.async_turn_on(effect="Вечеринка (цветомузыка)"))
    assert session.post.await_args.args[0].endswith("/operations")
    assert session.post.await_args.kwargs["json"]["operations"][0]["payload"] == {
        "animation_type": "color_music", "animation": {"id": "party"}
    }
    asyncio.run(entity.async_turn_on(effect="Вечеринка"))
    assert session.post.await_args.args[0].endswith("/actions")
    assert session.post.await_args.kwargs["json"]["actions"][0]["state"]["value"] == {
        "current_animation_type": "scene",
        "animations": {"scene": {"variant": "party", "variants": [{"id": "party", "options": []}]}},
    }

    value = animation["state"]["value"]
    value["current_animation_type"] = "scene"
    value["animations"]["scene"] = {"variant": "party"}
    quasar.dispatch_update(device["id"], device)
    assert entity.effect == "Вечеринка"

    value["current_animation_type"] = "color_music"
    value["animations"]["color_music"]["variant"] = "night"
    quasar.dispatch_update(device["id"], device)
    assert entity.effect is None  # Ordinary scene IDs are not musical variants.

    value["animations"]["color_music"]["variant"] = "future_music"
    quasar.dispatch_update(device["id"], device)
    assert entity.effect == "future_music"
    quasar.dispatch_update(
        device["id"],
        {"state": "online", "capabilities": [device["capabilities"][1]]},
    )
    assert entity.effect == "future_music"  # Brightness-only update.

    value["animations"]["color_music"] = {}
    quasar.dispatch_update(device["id"], device)
    assert entity.effect is None


def test_music_selection_preserves_variant_options_and_turns_on():
    device = ambi_device()
    device["capabilities"][0]["state"]["value"] = False
    music = device["capabilities"][3]["state"]["value"]["animations"]["color_music"]
    music["variants"] = [
        {
            "id": "gaming",
            "options": [{"instance": "autoplay", "enabled": False}],
        }
    ]
    original = deepcopy(device)
    session = AsyncMock()
    session.post.return_value.json.return_value = {"status": "ok"}
    session.get.return_value.json.return_value = {"status": "ok", **device}
    entity = YandexLight(YandexQuasar(session), device)

    asyncio.run(entity.async_turn_on(effect="Игра", brightness=255))

    assert len(session.post.await_args_list) == 2
    operation_call, power_call = session.post.await_args_list
    assert operation_call.args[0].endswith("/devices/synthetic-ambi/operations")
    operation = operation_call.kwargs["json"]["operations"][0]
    assert operation["payload"] == {
        "animation_type": "color_music",
        "animation": {
            "id": "gaming",
            "options": [{"instance": "autoplay", "enabled": False}],
        },
    }
    assert power_call.args[0].endswith("/devices/synthetic-ambi/actions")
    assert {
        action["state"]["instance"]: action["state"]["value"]
        for action in power_call.kwargs["json"]["actions"]
    } == {"on": True, "brightness": 100}
    assert device == original


def test_failed_music_operation_does_not_power_on():
    device = ambi_device()
    device["capabilities"][0]["state"]["value"] = False
    session = AsyncMock()
    session.post.return_value.json.return_value = {
        "operations": [{"result": {"status": "ERROR"}}],
    }
    session.get.return_value.json.return_value = {"status": "ok", **device}
    entity = YandexLight(YandexQuasar(session), device)

    with pytest.raises(HomeAssistantError, match="ERROR"):
        asyncio.run(entity.async_turn_on(effect="Вечеринка", brightness=255))

    session.post.assert_awaited_once()
    assert session.post.await_args.args[0].endswith("/operations")
    session.get.assert_not_awaited()
    assert not entity.is_on


@pytest.mark.parametrize("failure", ["rejected", "post_timeout", "refresh_timeout"])
def test_music_command_failure_keeps_confirmed_state(failure):
    device = ambi_device()
    session = AsyncMock()
    session.post.return_value.json.return_value = {"status": "ok"}
    if failure == "rejected":
        session.post.return_value.json.return_value = {"status": "error"}
    elif failure == "post_timeout":
        session.post.side_effect = TimeoutError("synthetic POST timeout")
    else:
        session.get.side_effect = TimeoutError("synthetic refresh timeout")
    entity = YandexLight(YandexQuasar(session), device)

    with pytest.raises(HomeAssistantError):
        asyncio.run(entity.async_turn_on(effect="Игра"))

    assert entity.effect == "Вечеринка"
    assert entity.is_on
    session.post.assert_awaited_once()
    if failure != "refresh_timeout":
        session.get.assert_not_awaited()


def test_music_capability_without_color_or_animation_state():
    device = ambi_device()
    del device["capabilities"][2]
    animation = device["capabilities"][2]
    animation["state"] = None
    session = AsyncMock()
    session.post.return_value.json.return_value = {"status": "ok"}
    session.get.return_value.json.return_value = {"status": "ok", **device}
    entity = YandexLight(YandexQuasar(session), device)
    assert entity.supported_color_modes == {ColorMode.BRIGHTNESS}
    assert entity.effect_list == ["Эквалайзер", "Вечеринка", "Игра"]
    assert entity.effect is None

    asyncio.run(entity.async_turn_on(effect="Эквалайзер"))

    assert session.post.await_args.args[0].endswith("/operations")
    assert session.post.await_args.kwargs["json"]["operations"][0]["payload"] == {
        "animation_type": "color_music",
        "animation": {"id": "equalizer"},
    }


def test_music_to_regular_color_transition():
    device = ambi_device()
    quasar = YandexQuasar(None)
    entity = YandexLight(quasar, device)
    value = device["capabilities"][3]["state"]["value"]
    value["current_animation_type"] = "color"
    value["animations"]["color"] = {
        "variant": "blue",
        "internal_state": {
            "instance": "hsv",
            "value": {"h": 225, "s": 55, "v": 90},
        },
    }
    quasar.dispatch_update(device["id"], device)
    assert entity.effect == "Синий"
    assert entity.hs_color == (225, 55)
    assert entity.color_mode == ColorMode.HS

    value["animations"]["color"] = {
        "internal_state": {"instance": "temperature_k", "value": 3000}
    }
    quasar.dispatch_update(device["id"], device)
    assert entity.effect is None
    assert entity.color_temp_kelvin == 3000
    assert entity.color_mode == ColorMode.COLOR_TEMP


@pytest.mark.parametrize(
    ("color", "effect", "hs_color", "color_temp", "color_mode"),
    [
        (
            {"id": "blue", "name": "Синий", "value": {"h": 225, "s": 55, "v": 90}},
            "Синий", (225, 55), None, ColorMode.HS,
        ),
        (
            {"value": {"h": 210, "s": 70, "v": 100}},
            None, (210, 70), None, ColorMode.HS,
        ),
        (
            {"value": 3000},
            None, None, 3000, ColorMode.COLOR_TEMP,
        ),
        (
            {"id": "night", "name": "Ночь"},
            "Ночь", None, None, ColorMode.UNKNOWN,
        ),
    ],
)
def test_music_none_uses_reported_legacy_color(
    color, effect, hs_color, color_temp, color_mode
):
    device = ambi_device()
    quasar = YandexQuasar(None)
    entity = YandexLight(quasar, device)
    assert entity.effect == "Вечеринка"
    device["capabilities"][3]["state"]["value"]["current_animation_type"] = "none"
    device["capabilities"][2]["state"]["value"] = color

    quasar.dispatch_update(device["id"], device)

    assert entity.effect == effect
    assert entity.hs_color == hs_color
    assert entity.color_temp_kelvin == color_temp
    assert entity.color_mode == color_mode


def test_music_none_without_color_clears_effect_but_keeps_saved_options():
    device = ambi_device()
    music = device["capabilities"][3]["state"]["value"]["animations"]["color_music"]
    music["variants"] = [{
        "id": "party", "options": [{"instance": "autoplay", "enabled": False}]
    }]
    session = AsyncMock()
    session.post.return_value.json.return_value = {"status": "ok"}
    session.get.return_value.json.return_value = {"status": "ok", **device}
    quasar = YandexQuasar(session)
    entity = YandexLight(quasar, device)

    quasar.dispatch_update(device["id"], {
        "state": "online", "capabilities": [device["capabilities"][1]],
    })
    assert entity.effect == "Вечеринка"

    animation = deepcopy(device["capabilities"][3])
    animation["state"]["value"]["current_animation_type"] = "none"
    quasar.dispatch_update(device["id"], {
        "state": "online", "capabilities": [animation],
    })
    assert entity.effect is None

    asyncio.run(entity.async_turn_on(effect="Вечеринка"))

    operation = session.post.await_args.kwargs["json"]["operations"][0]
    assert operation["payload"] == {
        "animation_type": "color_music",
        "animation": {
            "id": "party",
            "options": [{"instance": "autoplay", "enabled": False}],
        },
    }
