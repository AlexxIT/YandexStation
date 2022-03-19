import pytest
from homeassistant.components.water_heater import *

from custom_components.yandex_station.water_heater import YandexKettle


class Quasar:
    def __init__(self, data: dict):
        self.data = data

    async def get_device(self, *args):
        return self.data


@pytest.mark.asyncio
async def test_water_heater1():
    data = {
        "id": "xxx",
        "name": "Чайник",
        "state": "online",
        "capabilities": [{
            "retrievable": True,
            "type": "devices.capabilities.on_off",
            "state": {"instance": "on", "value": False},
            "parameters": {"split": False}
        }, {
            "retrievable": True,
            "type": "devices.capabilities.range",
            "state": {"instance": "temperature", "value": 100},
            "parameters": {
                "instance": "temperature",
                "name": "температура",
                "unit": "unit.temperature.celsius",
                "random_access": True, "looped": False,
                "range": {"min": 30, "max": 100, "precision": 5}
            }
        }, {
            "retrievable": False,
            "type": "devices.capabilities.mode",
            "state": None,
            "parameters": {
                "instance": "tea_mode", "name": "чай",
                "modes": [
                    {"value": "white_tea", "name": "Белый чай"},
                    {"value": "green_tea", "name": "Зеленый чай"},
                    {"value": "red_tea", "name": "Красный чай"},
                    {"value": "herbal_tea", "name": "Травяной чай"},
                    {"value": "flower_tea", "name": "Цветочный чай"},
                    {"value": "puerh_tea", "name": "Чай пуэр"},
                    {"value": "oolong_tea", "name": "Чай улун"},
                    {"value": "black_tea", "name": "Черный чай"}
                ]
            }
        }, {
            "retrievable": True,
            "type": "devices.capabilities.toggle",
            "state": {"instance": "mute", "value": False},
            "parameters": {"instance": "mute", "name": "без звука"}
        }, {
            "retrievable": True,
            "type": "devices.capabilities.toggle",
            "state": {"instance": "keep_warm", "value": False},
            "parameters": {
                "instance": "keep_warm", "name": "поддержание тепла"
            }
        }, {
            "retrievable": True,
            "type": "devices.capabilities.toggle",
            "state": {"instance": "backlight", "value": True},
            "parameters": {"instance": "backlight", "name": "подсветка"}
        }],
        "properties": [{
            "type": "devices.properties.float",
            "retrievable": True,
            "reportable": False,
            "parameters": {
                "instance": "temperature",
                "name": "температура",
                "unit": "unit.temperature.celsius"
            },
            "state": None,
            "state_changed_at": "2022-02-17T18:53:21Z",
            "last_updated": "2022-02-17T18:56:21Z"
        }],
    }

    # noinspection PyTypeChecker
    kettle = YandexKettle(Quasar(data), data)
    await kettle.async_update()

    assert kettle.min_temp == 30
    assert kettle.max_temp == 100
    assert kettle.precision == 5
    assert kettle.operation_list == [
        'on', 'off', 'white_tea', 'green_tea', 'red_tea', 'herbal_tea',
        'flower_tea', 'puerh_tea', 'oolong_tea', 'black_tea',
    ]
    assert kettle.supported_features == (
            SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
            SUPPORT_AWAY_MODE
    )

    assert kettle.available is True
    assert kettle.current_operation == "off"
    assert kettle.target_temperature == 100
    assert kettle.is_away_mode_on is False
    assert kettle.current_temperature is None


@pytest.mark.asyncio
async def test_water_heater2():
    data = {
        "id": "xxx",
        "name": "Чайник",
        "state": "online",
        "capabilities": [{
            "retrievable": True,
            "type": "devices.capabilities.on_off",
            "state": {"instance": "on", "value": False},
            "parameters": {"split": False}
        }, {
            "retrievable": True,
            "type": "devices.capabilities.range",
            "state": {"instance": "temperature", "value": 90},
            "parameters": {
                "instance": "temperature",
                "name": "температура",
                "unit": "unit.temperature.celsius",
                "random_access": True,
                "looped": False,
                "range": {"min": 35, "max": 90, "precision": 1}
            }
        }, {
            "retrievable": True,
            "type": "devices.capabilities.toggle",
            "state": {"instance": "keep_warm", "value": False},
            "parameters": {
                "instance": "keep_warm", "name": "поддержание тепла"
            }
        }, {
            "retrievable": True,
            "type": "devices.capabilities.toggle",
            "state": {"instance": "backlight", "value": False},
            "parameters": {"instance": "backlight", "name": "подсветка"}
        }],
        "properties": [{
            "type": "devices.properties.float",
            "retrievable": True,
            "reportable": True,
            "parameters": {
                "instance": "temperature",
                "name": "температура",
                "unit": "unit.temperature.celsius"
            },
            "state": {"percent": None, "status": None, "value": 39},
            "state_changed_at": "2022-03-19T16:39:23Z",
            "last_updated": "2022-03-19T16:39:23Z"
        }],
    }

    # noinspection PyTypeChecker
    kettle = YandexKettle(Quasar(data), data)
    await kettle.async_update()

    assert kettle.min_temp == 35
    assert kettle.max_temp == 90
    assert kettle.precision == 1
    assert kettle.operation_list == ['on', 'off']
    assert kettle.supported_features == (
            SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
            SUPPORT_AWAY_MODE
    )

    assert kettle.available is True
    assert kettle.current_operation == "off"
    assert kettle.target_temperature == 90
    assert kettle.is_away_mode_on is False
    assert kettle.current_temperature == 39
