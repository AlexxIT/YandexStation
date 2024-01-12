from custom_components.yandex_station.switch import YandexSwitch
from . import true, false, update_ha_state


def test_switch():
    device = {
        "id": "xxx",
        "name": "Выключатель",
        "type": "devices.types.switch",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.switch.svg/orig",
        "capabilities": [
            {
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
            }
        ],
        "properties": [],
        "item_type": "device",
        "skill_id": "xxx",
        "unconfigured": true,
        "state": "online",
        "created": "2023-04-15T05:32:58Z",
        "parameters": {
            "device_info": {"manufacturer": "ectoStroy", "model": "ES-ECTO-32"}
        },
    }

    state = update_ha_state(YandexSwitch, device)
    assert state.state == "on"
    assert state.attributes == {"friendly_name": "Выключатель"}


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
