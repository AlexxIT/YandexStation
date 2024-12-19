from homeassistant.components.humidifier import HumidifierEntityFeature

from custom_components.yandex_station.humidifier import YandexHumidifier
from . import false, null, true, update_ha_state


def test_humidifier_deerma():
    if not hasattr(YandexHumidifier, "current_humidity"):
        return  # support old HA version

    device = {
        "id": "xxx",
        "name": "Увлажнитель",
        "type": "devices.types.humidifier",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.humidifier.svg/orig",
        "capabilities": [
            {
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "fan_speed", "value": "high"},
                "parameters": {
                    "instance": "fan_speed",
                    "name": "скорость вентиляции",
                    "modes": [
                        {"value": "low", "name": "Низкая"},
                        {"value": "medium", "name": "Средняя"},
                        {"value": "high", "name": "Высокая"},
                    ],
                },
            },
        ],
        "properties": [
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "humidity",
                    "name": "влажность",
                    "unit": "unit.percent",
                },
                "state": {"percent": 52, "status": "normal", "value": 52},
                "state_changed_at": "2024-01-07T08:04:20Z",
                "last_updated": "2024-01-07T08:05:35Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                },
                "state": {"percent": null, "status": null, "value": 21},
                "state_changed_at": "2024-01-07T07:56:38Z",
                "last_updated": "2024-01-07T08:05:35Z",
            },
        ],
        "item_type": "device",
        "skill_id": "ad26f8c2-fc31-4928-a653-d829fda7e6c2",
        "room_name": "Спальня",
        "state": "online",
        "created": "2024-01-07T07:47:34Z",
        "parameters": {
            "device_info": {
                "manufacturer": "deerma",
                "model": "deerma.humidifier.jsqs",
                "sw_version": "2.1.3.0025",
            }
        },
    }

    state = update_ha_state(YandexHumidifier, device, config={})
    assert state.state == "on"
    assert state.attributes == {
        "available_modes": ["low", "medium", "high"],
        "current_humidity": 52,
        "friendly_name": "Увлажнитель",
        "max_humidity": 100,
        "min_humidity": 0,
        "mode": "high",
        "supported_features": HumidifierEntityFeature.MODES,
    }


def test_humidifier_polaris():
    if not hasattr(YandexHumidifier, "current_humidity"):
        return  # support old HA version

    # https://github.com/AlexxIT/YandexStation/pull/205
    device = {
        "id": "xxx",
        "name": "Увлажнитель",
        "type": "devices.types.humidifier",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.humidifier.svg/orig",
        "capabilities": [
            {
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "humidity", "value": 40},
                "parameters": {
                    "instance": "humidity",
                    "name": "влажность",
                    "unit": "unit.percent",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 30, "max": 75, "precision": 5},
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "work_speed", "value": "auto"},
                "parameters": {
                    "instance": "work_speed",
                    "name": "скорость работы",
                    "modes": [
                        {"value": "auto", "name": "Авто"},
                        {"value": "low", "name": "Низкая"},
                        {"value": "medium", "name": "Средняя"},
                        {"value": "high", "name": "Высокая"},
                        {"value": "turbo", "name": "Турбо"},
                    ],
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.toggle",
                "state": {"instance": "mute", "value": false},
                "parameters": {"instance": "mute", "name": "без звука"},
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.toggle",
                "state": {"instance": "controls_locked", "value": false},
                "parameters": {
                    "instance": "controls_locked",
                    "name": "блокировка управления",
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.toggle",
                "state": {"instance": "ionization", "value": false},
                "parameters": {"instance": "ionization", "name": "ионизация"},
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.toggle",
                "state": {"instance": "backlight", "value": false},
                "parameters": {"instance": "backlight", "name": "подсветка"},
            },
        ],
        "properties": [
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                },
                "state": {"percent": null, "status": null, "value": 0},
                "last_updated": "2024-01-11T13:58:58Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "humidity",
                    "name": "влажность",
                    "unit": "unit.percent",
                },
                "state": {"percent": 0, "status": "danger", "value": 0},
                "last_updated": "2024-01-11T13:58:58Z",
            },
        ],
        "item_type": "device",
        "room_name": "Дача",
        "state": "online",
        "created": "2024-01-11T13:58:58Z",
        "parameters": {
            "device_info": {
                "manufacturer": "polaris",
                "model": "PUH-9105",
                "hw_version": "",
                "sw_version": "",
            }
        },
    }

    state = update_ha_state(YandexHumidifier, device, config={})
    assert state.state == "on"
    assert state.attributes == {
        "available_modes": ["auto", "low", "medium", "high", "turbo"],
        "current_humidity": 0,
        "friendly_name": "Увлажнитель",
        "humidity": 40,
        "max_humidity": 75,
        "min_humidity": 30,
        "mode": "auto",
        "supported_features": HumidifierEntityFeature.MODES,
    }
