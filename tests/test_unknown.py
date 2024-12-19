from . import false, true


def test_washing_machine():
    device = {
        "id": "xxx",
        "name": "Стиральная машина",
        "names": ["Стиральная машина"],
        "type": "devices.types.washing_machine",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.washing_machine.svg/orig",
        "state": "offline",
        "groups": [],
        "room": "Ванная",
        "capabilities": [
            {
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
            },
            {
                "retrievable": true,
                "type": "devices.capabilities.toggle",
                "state": {"instance": "pause", "value": true},
                "parameters": {"instance": "pause", "name": "пауза"},
            },
        ],
        "properties": [],
        "skill_id": "xxx",
        "external_id": "xxx",
        "favorite": false,
    }
