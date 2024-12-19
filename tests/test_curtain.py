from . import false, null, true


def test_curtain():
    device = {
        "id": "xxx",
        "name": "Xiaomi Smart Curtain Motor",
        "type": "devices.types.openable.curtain",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.openable.curtain.svg/orig",
        "capabilities": [
            {
                "retrievable": false,
                "type": "devices.capabilities.on_off",
                "state": null,
                "parameters": {"split": true},
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "open", "value": 100},
                "parameters": {
                    "instance": "open",
                    "name": "открытие",
                    "unit": "unit.percent",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 0, "max": 100, "precision": 1},
                },
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
                "state": {"percent": 50, "status": "warning", "value": 50},
                "state_changed_at": "2024-01-05T14:19:29Z",
                "last_updated": "2024-01-07T09:53:08Z",
            }
        ],
        "item_type": "device",
        "skill_id": "xxx",
        "unconfigured": true,
        "state": "online",
        "created": "2023-11-17T15:45:41Z",
        "parameters": {
            "device_info": {
                "manufacturer": "lumi",
                "model": "lumi.curtain.hmcn02",
                "sw_version": "2.0.2_0036.0048",
            }
        },
    }


def test_curtain2():
    device = {
        "id": "xxx",
        "name": "Левая штора",
        "type": "devices.types.openable.curtain",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.openable.curtain.svg/orig",
        "capabilities": [
            {
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
            },
            {
                "reportable": false,
                "retrievable": true,
                "type": "devices.capabilities.range",
                "state": {"instance": "open", "value": 100},
                "parameters": {
                    "instance": "open",
                    "name": "открытие",
                    "unit": "unit.percent",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": 0, "max": 100, "precision": 1},
                },
            },
            {
                "reportable": false,
                "retrievable": false,
                "type": "devices.capabilities.toggle",
                "state": null,
                "parameters": {"instance": "pause", "name": "пауза"},
            },
        ],
        "properties": [],
        "item_type": "device",
        "skill_id": "xxx",
        "state": "online",
        "parameters": {
            "device_info": {
                "manufacturer": "IKEA",
                "model": "Zigbee: E1757, FYRTUR block-out roller blind",
                "sw_version": "34",
            }
        },
    }
