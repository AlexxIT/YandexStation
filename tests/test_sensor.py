from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfTemperature

from custom_components.yandex_station.sensor import YandexCustomSensor
from . import true, false, null, update_ha_state


def test_sensor():
    device = {
        "id": "xxx",
        "name": "Кабинет Градусник",
        "type": "devices.types.sensor",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.sensor.svg/orig",
        "capabilities": [],
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
                "state": {"percent": null, "status": null, "value": 19.5},
                "state_changed_at": "2024-01-07T09:55:04Z",
                "last_updated": "2024-01-07T09:55:04Z",
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
                "state": {"percent": 36, "status": "warning", "value": 36},
                "state_changed_at": "2024-01-07T09:55:04Z",
                "last_updated": "2024-01-07T09:55:04Z",
            },
        ],
        "item_type": "device",
        "skill_id": "xxx",
        "room_name": "Кабинет",
        "state": "online",
        "created": "2022-08-13T12:34:45Z",
        "parameters": {
            "device_info": {
                "manufacturer": "lumi",
                "model": "lumi.sensor_ht.v1",
                "sw_version": "1.0.0_0002",
            }
        },
    }

    config = next(
        i for i in device["properties"] if i["parameters"]["instance"] == "temperature"
    )

    state = update_ha_state(YandexCustomSensor, device, config=config)
    assert state.state == "19.5"
    assert state.attributes == {
        "device_class": "temperature",
        "friendly_name": "Кабинет Градусник температура",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
    }


def test_sensor_yandex():
    device = {
        "id": "xxx",
        "name": "Датчик климата 1",
        "type": "devices.types.sensor.climate",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.other.svg/orig",
        "capabilities": [],
        "properties": [
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
                "state_changed_at": "2024-01-13T18:52:17Z",
                "last_updated": "2024-01-14T20:26:31Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": false,
                "reportable": true,
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                },
                "state": {"percent": null, "status": null, "value": 23.1},
                "state_changed_at": "2024-01-14T20:52:07Z",
                "last_updated": "2024-01-14T20:52:07Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": false,
                "reportable": true,
                "parameters": {
                    "instance": "humidity",
                    "name": "влажность",
                    "unit": "unit.percent",
                },
                "state": {"percent": 59, "status": "normal", "value": 59},
                "state_changed_at": "2024-01-14T20:26:31Z",
                "last_updated": "2024-01-14T20:26:31Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": false,
                "reportable": true,
                "parameters": {
                    "instance": "pressure",
                    "name": "давление",
                    "unit": "unit.pressure.mmhg",
                },
                "state": {"percent": null, "status": null, "value": 751},
                "state_changed_at": "2024-01-14T20:37:52Z",
                "last_updated": "2024-01-14T20:48:17Z",
            },
        ],
        "item_type": "device",
        "skill_id": "YANDEX_IO",
        "room_name": "Гостиная",
        "state": "online",
        "created": "2024-01-13T18:52:07Z",
        "parameters": {
            "device_info": {
                "manufacturer": "LUMI",
                "model": "lumi.sensor_ht.agl02",
                "hw_version": "1",
                "sw_version": "28",
            }
        },
    }
