from custom_components.yandex_station.switch import YandexSwitch
from . import false, null, true, update_ha_state


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


def test_socket_yandex():
    device = {
        "id": "xxx",
        "name": "Белая розетка",
        "type": "devices.types.socket",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.socket.svg/orig",
        "capabilities": [
            {
                "reportable": true,
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
                    "instance": "voltage",
                    "name": "текущее напряжение",
                    "unit": "unit.volt",
                },
                "state": {"percent": null, "status": null, "value": 227},
                "state_changed_at": "2024-01-14T12:08:46Z",
                "last_updated": "2024-01-14T12:09:44Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "power",
                    "name": "потребляемая мощность",
                    "unit": "unit.watt",
                },
                "state": {"percent": null, "status": null, "value": 0},
                "state_changed_at": "2024-01-11T05:00:58Z",
                "last_updated": "2024-01-14T12:09:44Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "amperage",
                    "name": "потребление тока",
                    "unit": "unit.ampere",
                },
                "state": {"percent": null, "status": null, "value": 0},
                "state_changed_at": "2024-01-11T05:00:58Z",
                "last_updated": "2024-01-14T12:09:44Z",
            },
        ],
        "item_type": "device",
        "skill_id": "T",
        "room_name": "Детская",
        "state": "online",
        "render_info": {"icon": {"id": "yandex.socket"}},
        "created": "2022-11-16T18:08:19Z",
        "parameters": {
            "device_info": {
                "manufacturer": "Yandex",
                "model": "YNDX-0007",
                "hw_version": "1.0",
                "sw_version": "1.0.4",
            }
        },
    }
