from homeassistant.components.climate import ClimateEntityFeature, HVACMode

from custom_components.yandex_station.climate import YandexClimate
from . import false, null, true, update_ha_state

# support tests on old HA
try:
    TURN_ON_OFF = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
except AttributeError:
    TURN_ON_OFF = 0


def test_thermostat_remote_rf():
    device = {
        "id": "xxx",
        "name": "Зал Кондиционер",
        "type": "devices.types.thermostat.ac",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.thermostat.ac.svg/orig",
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
                "state": {"instance": "temperature", "value": 17},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 17, "max": 30, "precision": 1},
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "fan_speed", "value": "auto"},
                "parameters": {
                    "instance": "fan_speed",
                    "name": "скорость вентиляции",
                    "modes": [
                        {"value": "auto", "name": "Авто"},
                        {"value": "low", "name": "Низкая"},
                        {"value": "medium", "name": "Средняя"},
                        {"value": "high", "name": "Высокая"},
                    ],
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "thermostat", "value": "cool"},
                "parameters": {
                    "instance": "thermostat",
                    "name": "термостат",
                    "modes": [
                        {"value": "cool", "name": "Охлаждение"},
                        {"value": "fan_only", "name": "Вентиляция"},
                        {"value": "dry", "name": "Осушение"},
                        {"value": "auto", "name": "Авто"},
                    ],
                },
            },
        ],
        "properties": [],
        "item_type": "device",
        "skill_id": "T",
        "room_name": "Зал",
        "state": "online",
        "created": "2021-07-29T17:49:37Z",
        "parameters": {
            "device_info": {"manufacturer": "Неизвестно", "model": "Неизвестно"}
        },
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.state == "cool"
    assert state.attributes == {
        "current_temperature": None,
        "fan_mode": "auto",
        "fan_modes": ["auto", "low", "medium", "high"],
        "friendly_name": "Зал Кондиционер",
        "hvac_modes": [
            HVACMode.COOL,
            HVACMode.FAN_ONLY,
            HVACMode.DRY,
            HVACMode.AUTO,
            HVACMode.OFF,
        ],
        "max_temp": 30,
        "min_temp": 17,
        "supported_features": (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | TURN_ON_OFF
        ),
        "target_temp_step": 1,
        "temperature": 17,
    }


def test_thermostat_haier():
    # https://github.com/AlexxIT/YandexStation/issues/366
    device = {
        "id": "xxx",
        "name": "Кондиционер",
        "type": "devices.types.thermostat.ac",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.thermostat.ac.svg/orig",
        "state": "online",
        "room": "Гостиная",
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
                "state": {"instance": "temperature", "value": 24},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 16, "max": 30, "precision": 1},
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "program", "value": "cool"},
                "parameters": {
                    "instance": "program",
                    "name": "программа",
                    "modes": [
                        {"value": "cool", "name": "Охлаждение"},
                        {"value": "heat", "name": "Нагрев"},
                        {"value": "fan_only", "name": "Вентиляция"},
                        {"value": "dry", "name": "Осушение"},
                        {"value": "auto", "name": "Авто"},
                    ],
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "fan_speed", "value": "min"},
                "parameters": {
                    "instance": "fan_speed",
                    "name": "скорость вентиляции",
                    "modes": [
                        {"value": "auto", "name": "Авто"},
                        {"value": "max", "name": "Максимальный"},
                        {"value": "min", "name": "Минимальный"},
                        {"value": "normal", "name": "Нормальный"},
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
        ],
        "properties": [
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": false,
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                },
                "state": {"percent": null, "status": null, "value": 23},
                "state_changed_at": "2023-04-19T19:48:49Z",
                "last_updated": "2023-04-19T19:53:44Z",
            }
        ],
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.state == "cool"
    assert state.attributes == {
        "current_temperature": 23,
        "fan_mode": "min",
        "fan_modes": ["auto", "max", "min", "normal"],
        "friendly_name": "Кондиционер",
        "hvac_modes": [
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.FAN_ONLY,
            HVACMode.DRY,
            HVACMode.AUTO,
            HVACMode.OFF,
        ],
        "max_temp": 30,
        "min_temp": 16,
        "supported_features": (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | TURN_ON_OFF
        ),
        "target_temp_step": 1,
        "temperature": 24,
    }


def test_thermostat_tion():
    # https://github.com/AlexxIT/YandexStation/issues/307
    device = {
        "id": "xxx",
        "name": "Вентиляция",
        "type": "devices.types.thermostat",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.thermostat.svg/orig",
        "state": "online",
        "groups": [],
        "room": "Спальня",
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
                "state": {"instance": "temperature", "value": 25},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 0, "max": 25, "precision": 1},
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "fan_speed", "value": "low"},
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
        "properties": [],
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.state == "auto"
    assert state.attributes == {
        "current_temperature": None,
        "fan_mode": "low",
        "fan_modes": ["low", "medium", "high"],
        "friendly_name": "Вентиляция",
        "hvac_modes": [HVACMode.AUTO, HVACMode.OFF],
        "max_temp": 25,
        "min_temp": 0,
        "supported_features": (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | TURN_ON_OFF
        ),
        "target_temp_step": 1,
        "temperature": 25,
    }


def test_thermostat_ecto():
    device = {
        "id": "xxx",
        "name": "Гостиная 2",
        "type": "devices.types.thermostat",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.thermostat.svg/orig",
        "capabilities": [
            {
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "temperature", "value": 17},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 0, "max": 99, "precision": 1},
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "program", "value": "eco"},
                "parameters": {
                    "instance": "program",
                    "name": "программа",
                    "modes": [
                        {"value": "auto", "name": "Авто"},
                        {"value": "max", "name": "Максимальный"},
                        {"value": "normal", "name": "Нормальный"},
                        {"value": "eco", "name": "Эко"},
                    ],
                },
            },
        ],
        "properties": [],
        "item_type": "device",
        "unconfigured": true,
        "state": "online",
        "created": "2023-04-15T05:32:57Z",
        "parameters": {
            "device_info": {"manufacturer": "ectoStroy", "model": "ES-ECTO-32"}
        },
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.state == "auto"
    assert state.attributes == {
        "current_temperature": None,
        "friendly_name": "Гостиная 2",
        "hvac_modes": [HVACMode.AUTO],
        "max_temp": 99,
        "min_temp": 0,
        "preset_mode": "eco",
        "preset_modes": ["auto", "max", "normal", "eco"],
        "supported_features": (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | TURN_ON_OFF
        ),
        "target_temp_step": 1,
        "temperature": 17,
    }


def test_thermostat_heat():
    # https://github.com/AlexxIT/YandexStation/issues/210
    device = {
        "id": "xxx",
        "name": "Heat",
        "type": "unknown",
        "capabilities": [
            {
                "retrievable": True,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": True},
                "parameters": {"split": False},
            },
            {
                "retrievable": True,
                "type": "devices.capabilities.range",
                "state": {"instance": "temperature", "value": 40},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": True,
                    "looped": False,
                    "range": {"min": 35, "max": 75, "precision": 1},
                },
            },
            {
                "retrievable": True,
                "type": "devices.capabilities.mode",
                "state": {"instance": "heat", "value": "normal"},
                "parameters": {
                    "instance": "heat",
                    "name": "нагрев",
                    "modes": [
                        {"value": "low", "name": "Низкая"},
                        {"value": "normal", "name": "Нормальный"},
                        {"value": "turbo", "name": "Турбо"},
                    ],
                },
            },
        ],
        "properties": [],
        "state": "online",
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.state == "heat"
    assert state.attributes == {
        "current_temperature": None,
        "friendly_name": "Heat",
        "hvac_modes": [HVACMode.HEAT, HVACMode.OFF],
        "max_temp": 75,
        "min_temp": 35,
        "preset_mode": "normal",
        "preset_modes": ["low", "normal", "turbo"],
        "supported_features": (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | TURN_ON_OFF
        ),
        "target_temp_step": 1,
        "temperature": 40,
    }


def test_thermostat_aqara():
    device = {
        "id": "xxx",
        "name": "Термостат",
        "names": ["Термостат"],
        "type": "devices.types.thermostat",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.thermostat.svg/orig",
        "state": "online",
        "groups": [],
        "room": "Кухня",
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
                "state": {"instance": "temperature", "value": 25},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 5, "max": 30, "precision": 0.5},
                },
            },
        ],
        "properties": [
            {
                "type": "devices.properties.float",
                "retrievable": false,
                "reportable": true,
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                },
                "state": {"percent": null, "status": null, "value": 20.7},
                "state_changed_at": "2024-01-11T16:36:08Z",
                "last_updated": "2024-01-11T16:36:08Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": false,
                "reportable": true,
                "parameters": {
                    "instance": "battery_level",
                    "name": "уровень заряда",
                    "unit": "unit.percent",
                },
                "state": {"percent": 100, "status": "normal", "value": 100},
                "state_changed_at": "2024-01-11T15:50:12Z",
                "last_updated": "2024-01-11T15:51:01Z",
            },
        ],
        "skill_id": "YANDEX_IO",
        "external_id": "iot_zigbee_XXX",
        "favorite": false,
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.state == "auto"
    assert state.attributes == {
        "current_temperature": 20.7,
        "friendly_name": "Термостат",
        "hvac_modes": [HVACMode.AUTO, HVACMode.OFF],
        "max_temp": 30,
        "min_temp": 5,
        "supported_features": ClimateEntityFeature.TARGET_TEMPERATURE | TURN_ON_OFF,
        "target_temp_step": 0.5,
        "temperature": 25,
    }


def test_thermostat_viaomi():
    device = {
        "id": "xxx",
        "name": "грелка",
        "type": "devices.types.thermostat",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.thermostat.svg/orig",
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
                "type": "devices.capabilities.range",
                "state": {"instance": "temperature", "value": 35},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 5, "max": 35, "precision": 1},
                },
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "heat", "value": "min"},
                "parameters": {
                    "instance": "heat",
                    "name": "нагрев",
                    "modes": [
                        {"value": "min", "name": "Минимальный"},
                        {"value": "turbo", "name": "Турбо"},
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
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                },
                "state": {"percent": null, "status": null, "value": 20},
                "state_changed_at": "2024-01-12T16:11:37Z",
                "last_updated": "2024-01-12T16:29:28Z",
            }
        ],
        "state": "online",
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.state == "heat"
    assert state.attributes == {
        "current_temperature": 20,
        "friendly_name": "грелка",
        "hvac_modes": [HVACMode.HEAT, HVACMode.OFF],
        "max_temp": 35,
        "min_temp": 5,
        "preset_mode": "min",
        "preset_modes": ["min", "turbo"],
        "supported_features": (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | TURN_ON_OFF
        ),
        "target_temp_step": 1,
        "temperature": 35,
    }


def test_purifier_ballu():
    device = {
        "id": "xxx",
        "name": "Бризер",
        "names": ["Бризер"],
        "type": "devices.types.purifier",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.purifier.svg/orig",
        "state": "online",
        "groups": [],
        "room": "Спальня",
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
                "state": {"instance": "temperature", "value": 10},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 5, "max": 25, "precision": 1},
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "fan_speed", "value": "high"},
                "parameters": {
                    "instance": "fan_speed",
                    "name": "скорость вентиляции",
                    "modes": [
                        {"value": "auto", "name": "Авто"},
                        {"value": "low", "name": "Низкая"},
                        {"value": "medium", "name": "Средняя"},
                        {"value": "high", "name": "Высокая"},
                        {"value": "quiet", "name": "Тихий"},
                        {"value": "turbo", "name": "Турбо"},
                    ],
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
                        {"value": "quiet", "name": "Тихий"},
                        {"value": "turbo", "name": "Турбо"},
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
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                },
                "state": {"percent": null, "status": null, "value": 11},
                "state_changed_at": "2024-01-10T14:02:23Z",
                "last_updated": "2024-01-10T14:03:06Z",
            }
        ],
        "skill_id": "xxx",
        "external_id": "xxx",
        "favorite": false,
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.state == "fan_only"
    assert state.attributes == {
        "current_temperature": 11,
        "fan_mode": "high",
        "fan_modes": ["auto", "low", "medium", "high", "quiet", "turbo"],
        "friendly_name": "Бризер",
        "hvac_modes": [HVACMode.FAN_ONLY, HVACMode.OFF],
        "max_temp": 25,
        "min_temp": 5,
        "preset_mode": "auto",
        "preset_modes": ["auto", "quiet", "turbo"],
        "supported_features": (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | TURN_ON_OFF
        ),
        "target_temp_step": 1,
        "temperature": 10,
    }


def test_purifier_xiaomi():
    device = {
        "id": "xxx",
        "name": "Очиститель",
        "type": "devices.types.purifier",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.purifier.svg/orig",
        "capabilities": [
            {
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
            }
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
                "state": {"percent": 28, "status": "warning", "value": 28},
                "state_changed_at": "2024-01-07T10:26:15Z",
                "last_updated": "2024-01-07T10:26:15Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "pm2.5_density",
                    "name": "уровень частиц PM2.5",
                    "unit": "unit.density.mcg_m3",
                },
                "state": {"percent": null, "status": null, "value": 2},
                "state_changed_at": "2024-01-07T06:08:34Z",
                "last_updated": "2024-01-07T09:53:08Z",
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
                "state": {"percent": null, "status": null, "value": 23.9},
                "state_changed_at": "2024-01-07T10:25:26Z",
                "last_updated": "2024-01-07T10:25:26Z",
            },
        ],
        "item_type": "device",
        "skill_id": "xxx",
        "room_name": "Кухня",
        "state": "online",
        "created": "2022-08-13T12:34:44Z",
        "parameters": {
            "device_info": {
                "manufacturer": "zhimi",
                "model": "zhimi.airpurifier.ma2",
                "sw_version": "1.4.3_13109",
            }
        },
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.state == "fan_only"
    assert state.attributes == {
        "current_humidity": 28,
        "current_temperature": 23.9,
        "friendly_name": "Очиститель",
        "hvac_modes": [HVACMode.FAN_ONLY, HVACMode.OFF],
        "max_temp": 35,
        "min_temp": 7,
        "supported_features": TURN_ON_OFF,
    }


def test_thermostat_ballu():
    # https://github.com/AlexxIT/YandexStation/issues/514
    device = {
        "id": "xxx",
        "name": "Кондиционер",
        "type": "devices.types.thermostat.ac",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.thermostat.ac.svg/orig",
        "capabilities": [
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": false},
                "parameters": {"split": false},
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "temperature", "value": 16},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 16, "max": 30, "precision": 1},
                },
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "swing", "value": "auto"},
                "parameters": {
                    "instance": "swing",
                    "name": "направление воздуха",
                    "modes": [
                        {"value": "auto", "name": "Авто"},
                        {"value": "vertical", "name": "Вертикальный"},
                        {"value": "horizontal", "name": "Горизонтальный"},
                        {"value": "stationary", "name": "Статичный"},
                    ],
                },
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "work_speed", "value": "low"},
                "parameters": {
                    "instance": "work_speed",
                    "name": "скорость работы",
                    "modes": [
                        {"value": "auto", "name": "Авто"},
                        {"value": "low", "name": "Низкая"},
                        {"value": "medium", "name": "Средняя"},
                        {"value": "high", "name": "Высокая"},
                        {"value": "quiet", "name": "Тихий"},
                        {"value": "turbo", "name": "Турбо"},
                    ],
                },
            },
            {
                "reportable": true,
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "thermostat", "value": "auto"},
                "parameters": {
                    "instance": "thermostat",
                    "name": "термостат",
                    "modes": [
                        {"value": "cool", "name": "Охлаждение"},
                        {"value": "heat", "name": "Нагрев"},
                        {"value": "fan_only", "name": "Вентиляция"},
                        {"value": "dry", "name": "Осушение"},
                        {"value": "auto", "name": "Авто"},
                        {"value": "quiet", "name": "Тихий"},
                        {"value": "turbo", "name": "Турбо"},
                        {"value": "eco", "name": "Эко"},
                    ],
                },
            },
        ],
        "properties": [],
        "item_type": "device",
        "room_name": "Комната",
        "status_info": {
            "status": "online",
            "reportable": true,
            "updated": 1718753653.209784,
        },
        "state": "online",
        "created": "2024-06-16T20:56:14Z",
        "parameters": {
            "device_info": {
                "manufacturer": "Ballu",
                "model": "Discovery",
                "hw_version": "",
                "sw_version": "1.12",
            }
        },
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.attributes == {
        "current_temperature": None,
        "friendly_name": "Кондиционер",
        "hvac_modes": [
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.FAN_ONLY,
            HVACMode.DRY,
            HVACMode.AUTO,
            HVACMode.OFF,
        ],
        "max_temp": 30,
        "min_temp": 16,
        "preset_mode": "low",
        "preset_modes": ["auto", "low", "medium", "high", "quiet", "turbo"],
        "supported_features": ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | TURN_ON_OFF,
        "target_temp_step": 1,
        "temperature": 16,
    }


def test_elari():
    # https://github.com/AlexxIT/YandexStation/issues/615
    device = {
        "id": "xxx",
        "name": "Кондиционер зал",
        "type": "devices.types.thermostat.ac",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.thermostat.ac.svg/orig",
        "capabilities": [
            {
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
                "can_be_deferred": true,
            },
            {
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "temperature", "value": 24},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 16, "max": 30, "precision": 1},
                },
            },
            {
                "reportable": false,
                "retrievable": false,
                "type": "devices.capabilities.mode",
                "state": null,
                "parameters": {
                    "instance": "thermostat",
                    "name": "термостат",
                    "modes": [
                        {"value": "cool", "name": "Охлаждение"},
                        {"value": "heat", "name": "Нагрев"},
                        {"value": "fan_only", "name": "Вентиляция"},
                        {"value": "dry", "name": "Осушение"},
                        {"value": "auto", "name": "Авто"},
                    ],
                },
            },
        ],
        "properties": [],
        "item_type": "device",
        "skill_id": "43606352-ee3f-4ec8-a131-2c754551b4d2",
        "room_name": "Гостиная",
        "status_info": {
            "status": "online",
            "updated": 1737297234.556013,
            "changed": 1737209570.86133,
        },
        "state": "online",
        "created": "2023-09-14T18:23:00Z",
        "parameters": {
            "device_info": {
                "manufacturer": "ELARI",
                "model": "S06",
                "hw_version": "1.0",
                "sw_version": "1.0",
            }
        },
        "house_name": "Мой дом",
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.state == "unknown"
    assert state.attributes == {
        "current_temperature": None,
        "friendly_name": "Кондиционер зал",
        "hvac_modes": [
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.FAN_ONLY,
            HVACMode.DRY,
            HVACMode.AUTO,
            HVACMode.OFF,
        ],
        "max_temp": 30,
        "min_temp": 16,
        "supported_features": ClimateEntityFeature.TARGET_TEMPERATURE | TURN_ON_OFF,
        "target_temp_step": 1,
        "temperature": 24,
    }


def test_rusclimate():
    device = {
        "id": "xxx",
        "name": "Кондиционер",
        "type": "devices.types.thermostat.ac",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.thermostat.ac.svg/orig",
        "capabilities": [
            {
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
                "can_be_deferred": true,
            },
            {
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "temperature", "value": 25},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 16, "max": 32, "precision": 1},
                },
            },
            {
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "swing", "value": "stationary"},
                "parameters": {
                    "instance": "swing",
                    "name": "направление воздуха",
                    "modes": [
                        {"value": "auto", "name": "Авто"},
                        {"value": "vertical", "name": "Вертикальный"},
                        {"value": "horizontal", "name": "Горизонтальный"},
                        {"value": "stationary", "name": "Статичный"},
                    ],
                },
            },
            {
                "reportable": false,
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
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.mode",
                "state": {"instance": "thermostat", "value": "quiet"},
                "parameters": {
                    "instance": "thermostat",
                    "name": "термостат",
                    "modes": [
                        {"value": "cool", "name": "Охлаждение"},
                        {"value": "heat", "name": "Нагрев"},
                        {"value": "fan_only", "name": "Вентиляция"},
                        {"value": "dry", "name": "Осушение"},
                        {"value": "auto", "name": "Авто"},
                        {"value": "quiet", "name": "Тихий"},
                        {"value": "eco", "name": "Эко"},
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
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                },
                "state": {"percent": null, "status": null, "value": 25},
                "state_changed_at": "2025-02-10T15:07:21Z",
                "last_updated": "2025-02-10T15:09:52Z",
            }
        ],
        "item_type": "device",
        "skill_id": "b8deb65b-d522-4f02-8f65-52ccdd195bff",
        "room_name": "Кабинет",
        "status_info": {
            "status": "online",
            "updated": 1739200193.039044,
            "changed": 1739199088.236251,
        },
        "state": "online",
        "created": "2025-02-10T14:44:06Z",
        "parameters": {
            "device_info": {
                "manufacturer": "rusclimate",
                "model": "Shuft Berg/ MBO M-1",
                "hw_version": "",
                "sw_version": "",
            }
        },
        "house_name": "Дом",
    }

    state = update_ha_state(YandexClimate, device, config={})
    assert state.state == "unknown"
    assert state.attributes == {
        "current_temperature": 25,
        "friendly_name": "Кондиционер",
        "hvac_modes": [
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.FAN_ONLY,
            HVACMode.DRY,
            HVACMode.AUTO,
            HVACMode.OFF,
        ],
        "max_temp": 32,
        "min_temp": 16,
        "preset_mode": "auto",
        "preset_modes": ["auto", "low", "medium", "high", "turbo"],
        "supported_features": ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | TURN_ON_OFF,
        "target_temp_step": 1,
        "temperature": 25,
    }
