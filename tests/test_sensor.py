from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfTemperature

from custom_components.yandex_station.sensor import YandexCustomSensor
from . import true, null, update_ha_state


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
