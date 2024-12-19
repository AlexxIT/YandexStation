from homeassistant.components.vacuum import VacuumEntityFeature

from custom_components.yandex_station.vacuum import YandexVacuum
from . import false, true, update_ha_state


def test_roborock():
    device = {
        "id": "xxx",
        "name": "Пылесос",
        "type": "devices.types.vacuum_cleaner",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.vacuum_cleaner.svg/orig",
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
                "state": {"instance": "work_speed", "value": "fast"},
                "parameters": {
                    "instance": "work_speed",
                    "name": "скорость работы",
                    "modes": [
                        {"value": "fast", "name": "Быстрый"},
                        {"value": "normal", "name": "Нормальный"},
                        {"value": "quiet", "name": "Тихий"},
                        {"value": "turbo", "name": "Турбо"},
                    ],
                },
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.toggle",
                "state": {"instance": "pause", "value": false},
                "parameters": {"instance": "pause", "name": "пауза"},
            },
        ],
        "properties": [
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "battery_level",
                    "name": "уровень заряда",
                    "unit": "unit.percent",
                },
                "state": {"percent": 78, "status": "normal", "value": 78},
                "state_changed_at": "2023-12-12T00:43:08Z",
                "last_updated": "2023-12-12T00:52:55Z",
            }
        ],
        "item_type": "device",
        "skill_id": "xxx",
        "room_name": "Тест",
        "state": "online",
        "created": "2022-08-13T12:34:43Z",
        "parameters": {
            "device_info": {
                "manufacturer": "roborock",
                "model": "roborock.vacuum.s5e",
                "sw_version": "3.5.8_1530",
            }
        },
    }

    state = update_ha_state(YandexVacuum, device)
    assert state.state == "cleaning"
    assert state.attributes == {
        "battery_icon": "mdi:battery-80",
        "battery_level": 78,
        "fan_speed": "fast",
        "fan_speed_list": ["fast", "normal", "quiet", "turbo"],
        "friendly_name": "Пылесос",
        "supported_features": (
            VacuumEntityFeature.PAUSE
            | VacuumEntityFeature.STOP
            | VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.FAN_SPEED
            | VacuumEntityFeature.BATTERY
            | VacuumEntityFeature.START
        ),
    }
