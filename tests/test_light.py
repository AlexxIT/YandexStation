from homeassistant.components.light import ColorMode, LightEntityFeature

from custom_components.yandex_station.light import YandexLight
from . import false, null, true, update_ha_state


def fix_hass_2024_12(state):
    attrs = dict(state.attributes)
    attrs.pop("rgb_color")
    attrs.pop("xy_color")
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
        "color_mode": ColorMode.ONOFF,
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
        "color_mode": ColorMode.HS,
        "effect": "",
        "effect_list": [
            "Мягкий белый",
            "Теплый белый",
            "Белый",
            "Дневной белый",
            "Холодный белый",
        ],
        "friendly_name": "Лампа",
        "hs_color": (27.806, 56.57),
        # "rgb_color": (255, 177, 110),
        "supported_color_modes": [ColorMode.HS],
        "supported_features": LightEntityFeature.EFFECT,
        # "xy_color": (0.496, 0.383),
    }
