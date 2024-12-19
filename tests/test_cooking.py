from . import false, true


def test_cooking():
    device = {
        "id": "xxx",
        "name": "Мультиварка",
        "type": "devices.types.cooking.multicooker",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.cooking.multicooker.svg/orig",
        "capabilities": [
            {
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": false},
                "parameters": {"split": false},
            },
            {
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "temperature", "value": 100},
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 35, "max": 160, "precision": 5},
                },
            },
            {
                "reportable": false,
                "retrievable": false,
                "type": "devices.capabilities.mode",
                "state": {"instance": "program", "value": "aspic"},
                "parameters": {
                    "instance": "program",
                    "name": "программа",
                    "modes": [
                        {"value": "baking", "name": "Выпечка"},
                        {"value": "frying", "name": "Жарка"},
                        {"value": "cereals", "name": "Крупы"},
                        {"value": "milk_porridge", "name": "Молочная каша"},
                        {"value": "multicooker", "name": "Мультиповар"},
                        {"value": "steam", "name": "Пар"},
                        {"value": "pilaf", "name": "Плов"},
                        {"value": "soup", "name": "Суп"},
                        {"value": "stewing", "name": "Тушение"},
                        {"value": "aspic", "name": "Холодец"},
                    ],
                },
            },
            {
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.toggle",
                "state": {"instance": "controls_locked", "value": false},
                "parameters": {
                    "instance": "controls_locked",
                    "name": "блокировка управления",
                },
            },
            {
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.toggle",
                "state": {"instance": "keep_warm", "value": true},
                "parameters": {
                    "instance": "keep_warm",
                    "name": "поддержание тепла",
                },
            },
        ],
        "properties": [],
        "item_type": "device",
        "skill_id": "xxx",
        "room_name": "Спальня",
        "state": "online",
        "created": "2023-12-20T11:53:53Z",
        "parameters": {
            "device_info": {
                "manufacturer": "polaris",
                "model": "PMC-0524WIFI",
                "hw_version": "",
                "sw_version": "",
            }
        },
    }
