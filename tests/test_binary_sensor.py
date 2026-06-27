from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.yandex_station.binary_sensor import YandexBinarySensor
from . import FakeQuasar, true, update_ha_state


def test_yndx_00525_presence_sensor():
    device = {
        "id": "xxx",
        "name": "Датчик присутствия",
        "type": "devices.types.sensor.presence",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.sensor.svg/orig",
        "capabilities": [],
        "properties": [
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "occupancy",
                    "name": "количество объектов",
                    "unit": "unit.object_quantity",
                },
                "state": {
                    "percent": None,
                    "status": None,
                    "value": 1,
                },
                "state_changed_at": "2026-06-27T09:55:04Z",
                "last_updated": "2026-06-27T09:55:04Z",
            }
        ],
        "item_type": "device",
        "skill_id": "xxx",
        "room_name": "Кабинет",
        "state": "online",
        "created": "2026-06-27T09:55:04Z",
        "parameters": {
            "device_info": {
                "manufacturer": "Yandex",
                "model": "YNDX-00525",
            }
        },
    }

    state = update_ha_state(
        YandexBinarySensor, device, config=device["properties"][0]
    )
    assert state.state == "on"
    assert state.attributes == {
        "device_class": BinarySensorDeviceClass.OCCUPANCY,
        "friendly_name": "Датчик присутствия количество объектов",
    }


def test_yndx_00525_zone_entity_name():
    parent = {
        "id": "sensor",
        "name": "Датчик присутствия",
        "house_name": "Мой дом",
        "room_name": "Гостиная",
        "type": "devices.types.sensor.presence",
        "capabilities": [
            {"type": "devices.capabilities.planar_view", "retrievable": true}
        ],
        "properties": [
            {"parameters": {"instance": "illumination"}},
            {"parameters": {"instance": "occupancy"}},
        ],
        "parameters": {"device_info": {"model": "YNDX-00525"}},
    }
    zone = {
        "id": "zone",
        "name": "Диван",
        "house_name": "Мой дом",
        "room_name": "Гостиная",
        "type": "devices.types.sensor.presence",
        "capabilities": [
            {"type": "devices.capabilities.presence_zone", "retrievable": true}
        ],
        "properties": [
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "parameters": {
                    "instance": "occupancy",
                    "name": "присутствие",
                    "unit": "unit.object_quantity",
                },
                "state": {"value": 1},
            }
        ],
        "parameters": {"device_info": {"model": "YNDX-00525"}},
    }

    quasar = FakeQuasar(zone)
    quasar.devices = [parent, zone]
    entity = YandexBinarySensor(quasar, zone, zone["properties"][0])
    assert (
        entity.name
        == "Датчик присутствия - Диван присутствие"
    )
