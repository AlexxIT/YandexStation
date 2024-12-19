from homeassistant.components.media_player import MediaPlayerEntityFeature

from custom_components.yandex_station.media_player import YandexMediaPlayer
from . import false, null, true, update_ha_state


def test_tv_rf():
    device = {
        "id": "xxx",
        "name": "Зал Телевизор",
        "type": "devices.types.media_device.tv",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.media_device.tv.svg/orig",
        "capabilities": [
            {
                "retrievable": false,
                "type": "devices.capabilities.on_off",
                "state": null,
                "parameters": {"split": false},
            },
            {
                "retrievable": false,
                "type": "devices.capabilities.range",
                "state": null,
                "parameters": {
                    "instance": "volume",
                    "name": "громкость",
                    "unit": "",
                    "random_access": false,
                    "looped": false,
                },
            },
            {
                "retrievable": false,
                "type": "devices.capabilities.range",
                "state": null,
                "parameters": {
                    "instance": "channel",
                    "name": "канал",
                    "unit": "",
                    "random_access": true,
                    "looped": true,
                },
            },
            {
                "retrievable": false,
                "type": "devices.capabilities.mode",
                "state": null,
                "parameters": {
                    "instance": "input_source",
                    "name": "источник сигнала",
                    "modes": [
                        {"value": "one", "name": "Один"},
                        {"value": "two", "name": "Два"},
                    ],
                },
            },
            {
                "retrievable": false,
                "type": "devices.capabilities.toggle",
                "state": null,
                "parameters": {"instance": "mute", "name": "без звука"},
            },
            {
                "retrievable": false,
                "type": "devices.capabilities.toggle",
                "state": null,
                "parameters": {"instance": "pause", "name": "пауза"},
            },
        ],
        "properties": [],
        "item_type": "device",
        "skill_id": "T",
        "room_name": "Зал",
        "state": "online",
        "created": "2020-11-29T06:30:20Z",
        "parameters": {
            "device_info": {"manufacturer": "Неизвестно", "model": "Неизвестно"}
        },
    }

    state = update_ha_state(YandexMediaPlayer, device, config={})
    assert state.state == "idle"
    assert state.attributes == {
        "assumed_state": True,
        "device_class": "tv",
        "friendly_name": "Зал Телевизор",
        "icon": "mdi:television-classic",
        "source_list": ["Один", "Два"],
        "supported_features": (
            MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.PLAY
        ),
    }


def test_tv_lg():
    device = {
        "id": "xxx",
        "name": "Телевизор",
        "names": ["Телевизор"],
        "type": "devices.types.media_device.tv",
        "icon_url": "https://avatars.mds.yandex.net/get-iot/icons-devices-devices.types.media_device.tv.svg/orig",
        "state": "online",
        "groups": [],
        "room": "Комната",
        "capabilities": [
            {
                "retrievable": true,
                "type": "devices.capabilities.on_off",
                "state": {"instance": "on", "value": true},
                "parameters": {"split": false},
            },
            {
                "retrievable": false,
                "type": "devices.capabilities.range",
                "state": null,
                "parameters": {
                    "instance": "volume",
                    "name": "громкость",
                    "unit": "",
                    "random_access": true,
                    "looped": false,
                    "range": {"min": -100, "max": 100, "precision": 1},
                },
            },
            {
                "retrievable": false,
                "type": "devices.capabilities.range",
                "state": null,
                "parameters": {
                    "instance": "channel",
                    "name": "канал",
                    "unit": "",
                    "random_access": true,
                    "looped": false,
                },
            },
            {
                "retrievable": false,
                "type": "devices.capabilities.toggle",
                "state": null,
                "parameters": {"instance": "mute", "name": "без звука"},
            },
            {
                "retrievable": false,
                "type": "devices.capabilities.toggle",
                "state": null,
                "parameters": {"instance": "pause", "name": "пауза"},
            },
        ],
        "properties": [],
        "skill_id": "xxx",
        "external_id": "xxx_TV",
        "favorite": false,
    }

    state = update_ha_state(YandexMediaPlayer, device, config={})
    assert state.state == "on"
    assert state.attributes == {
        "device_class": "tv",
        "friendly_name": "Телевизор",
        "icon": "mdi:television-classic",
        "supported_features": (
            MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.PLAY
        ),
    }
