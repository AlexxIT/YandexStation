from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfTemperature

from custom_components.yandex_station.sensor import YandexCustomSensor
from . import false, null, true, update_ha_state


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


def test_sensor_qingping():
    # https://github.com/AlexxIT/YandexStation/issues/564
    device = {
        "id": "xxx",
        "name": "Датчик воздуха",
        "type": "devices.types.sensor",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.sensor.svg/orig",
        "capabilities": [],
        "properties": [
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "humidity",
                    "name": "влажность",
                    "unit": "unit.percent",
                },
                "state": {"percent": 33, "status": "warning", "value": 33},
                "state_changed_at": "2024-10-30T08:38:25Z",
                "last_updated": "2024-10-30T08:38:25Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "pm2.5_density",
                    "name": "уровень частиц PM2.5",
                    "unit": "unit.density.mcg_m3",
                },
                "state": {"percent": null, "status": null, "value": 5},
                "state_changed_at": "2024-10-29T02:24:23Z",
                "last_updated": "2024-10-29T02:25:08Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "pm10_density",
                    "name": "уровень частиц PM10",
                    "unit": "unit.density.mcg_m3",
                },
                "state": {"percent": null, "status": null, "value": 5},
                "state_changed_at": "2024-10-29T02:24:23Z",
                "last_updated": "2024-10-29T02:25:08Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "temperature",
                    "name": "температура",
                    "unit": "unit.temperature.celsius",
                },
                "state": {"percent": null, "status": null, "value": 24.5},
                "state_changed_at": "2024-10-30T08:38:25Z",
                "last_updated": "2024-10-30T08:48:25Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "co2_level",
                    "name": "уровень углекислого газа",
                    "unit": "unit.ppm",
                },
                "state": {"percent": 56, "status": "normal", "value": 786},
                "state_changed_at": "2024-10-30T08:48:25Z",
                "last_updated": "2024-10-30T08:48:25Z",
            },
            {
                "type": "devices.properties.float",
                "retrievable": true,
                "reportable": true,
                "parameters": {
                    "instance": "battery_level",
                    "name": "уровень заряда",
                    "unit": "unit.percent",
                },
                "state": {"percent": 38, "status": "warning", "value": 38},
                "state_changed_at": "2024-10-30T08:50:38Z",
                "last_updated": "2024-10-30T08:50:38Z",
            },
        ],
        "item_type": "device",
        "skill_id": "ad26f8c2-fc31-4928-a653-d829fda7e6c2",
        "room_name": "Офис",
        "status_info": {
            "status": "online",
            "reportable": true,
            "updated": 1730278238.566558,
            "changed": 1729827161.15856,
        },
        "state": "online",
        "created": "2024-10-24T04:42:40Z",
        "parameters": {
            "device_info": {
                "manufacturer": "cgllc",
                "model": "cgllc.airm.cgs2",
                "sw_version": "4.3.9_0137",
            }
        },
        "house_name": "Мой дом",
    }

    state = update_ha_state(YandexCustomSensor, device, config=device["properties"][0])
    assert state.state == "33"
    assert state.attributes == {
        "device_class": "humidity",
        "friendly_name": "Датчик воздуха влажность",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit_of_measurement": "%",
    }

    state = update_ha_state(YandexCustomSensor, device, config=device["properties"][1])
    assert state.state == "5"
    assert state.attributes == {
        "device_class": "pm25",
        "friendly_name": "Датчик воздуха уровень частиц PM2.5",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit_of_measurement": "µg/m³",
    }

    state = update_ha_state(YandexCustomSensor, device, config=device["properties"][2])
    assert state.state == "5"
    assert state.attributes == {
        "device_class": "pm10",
        "friendly_name": "Датчик воздуха уровень частиц PM10",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit_of_measurement": "µg/m³",
    }

    state = update_ha_state(YandexCustomSensor, device, config=device["properties"][3])
    assert state.state == "24.5"
    assert state.attributes == {
        "device_class": "temperature",
        "friendly_name": "Датчик воздуха температура",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
    }

    state = update_ha_state(YandexCustomSensor, device, config=device["properties"][4])
    assert state.state == "786"
    assert state.attributes == {
        "device_class": "carbon_dioxide",
        "friendly_name": "Датчик воздуха уровень углекислого газа",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit_of_measurement": "ppm",
    }

    state = update_ha_state(YandexCustomSensor, device, config=device["properties"][5])
    assert state.state == "38"
    assert state.attributes == {
        "device_class": "battery",
        "friendly_name": "Датчик воздуха уровень заряда",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit_of_measurement": "%",
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
