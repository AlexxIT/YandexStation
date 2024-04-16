import base64
import json

from homeassistant.components.sensor import DOMAIN

from custom_components.yandex_station.media_player import YandexStation
from tests import FakeQuasar

assert DOMAIN  # fix circular import bug


def encode_extra(value: dict) -> str:
    raw = json.dumps(value) + "\n"
    return base64.b64encode(raw.encode()).decode()


def _test_song():
    data = {
        "state": {
            "aliceState": "IDLE",
            "canStop": True,
            "hdmi": {"capable": False, "present": False},
            "playerState": {
                "duration": 288.0,
                "entityInfo": {
                    "description": "",
                    "id": "37232253",
                    "next": {"id": "", "type": "Track"},
                    "prev": {"id": "83530059", "type": "Track"},
                    "repeatMode": "None",
                    "shuffled": False,
                    "type": "Track",
                },
                "extra": {
                    "coverURI": "avatars.yandex.net/get-music-content/49876/a4be9993.a.4712278-1/%%",
                    "requestID": "xxx",
                    "stateType": "music",
                },
                "hasNext": True,
                "hasPause": True,
                "hasPlay": False,
                "hasPrev": True,
                "hasProgressBar": True,
                "id": "37232253",
                "liveStreamText": "",
                "playerType": "music_thin",
                "playlistDescription": "",
                "playlistId": "37232253",
                "playlistType": "Track",
                "progress": 48.0,
                "showPlayer": False,
                "subtitle": "Би-2",
                "title": "Пора возвращаться домой",
                "type": "Track",
            },
            "playing": True,
            "volume": 0.5,
            "local_push": True,
        }
    }

    device = {"id": "", "name": "", "quasar_info": {"device_id": "", "platform": ""}}
    # noinspection PyTypeChecker
    speaker = YandexStation(FakeQuasar(), device)
    speaker.async_set_state(data)

    assert speaker.media_artist == "Би-2"
    assert speaker.media_content_type == "music"
    assert speaker.media_duration == 288
    assert (
        speaker.media_image_url
        == "https://avatars.yandex.net/get-music-content/49876/a4be9993.a.4712278-1/400x400"
    )
    assert speaker.media_position == 48
    assert speaker.media_title == "Пора возвращаться домой"
    assert speaker.state == "playing"


def _test_radio():
    data = {
        "state": {
            "aliceState": "IDLE",
            "canStop": True,
            "hdmi": {"capable": False, "present": False},
            "playerState": {
                "duration": 0.0,
                "entityInfo": {
                    "description": "",
                    "id": "europa_plus",
                    "next": {"id": "32550129", "type": "Track"},
                    "prev": {"id": "24442530", "type": "Track"},
                    "repeatMode": "None",
                    "shuffled": False,
                    "type": "FM_RADIO",
                },
                "extra": {
                    "coverURI": "avatars.mds.yandex.net/get-music-misc/28592/europa_plus-225/%%",
                    "requestID": "xxx",
                    "stateType": "radio",
                },
                "hasNext": False,
                "hasPause": True,
                "hasPlay": False,
                "hasPrev": False,
                "hasProgressBar": False,
                "id": "europa_plus",
                "liveStreamText": "Прямой эфир",
                "playerType": "radio",
                "playlistDescription": "",
                "playlistId": "europa_plus",
                "playlistType": "FM_RADIO",
                "progress": 0.0,
                "showPlayer": False,
                "subtitle": "",
                "title": "Европа плюс",
                "type": "stream",
            },
            "playing": True,
            "volume": 0.5,
            "local_push": True,
        }
    }

    device = {"id": "", "name": "", "quasar_info": {"device_id": "", "platform": ""}}
    # noinspection PyTypeChecker
    speaker = YandexStation(FakeQuasar(), device)
    speaker.async_set_state(data)

    assert speaker.media_artist == ""
    assert speaker.media_content_type == "channel"
    assert speaker.media_duration == 0
    assert (
        speaker.media_image_url
        == "https://avatars.mds.yandex.net/get-music-misc/28592/europa_plus-225/400x400"
    )
    assert speaker.media_position == 0
    assert speaker.media_title == "Европа плюс"
    assert speaker.state == "playing"


def _test_youtube():
    data = {
        "state": {
            "aliceState": "IDLE",
            "canStop": True,
            "hdmi": {"capable": True, "present": True},
            "playerState": {
                "duration": 5140.0,
                "entityInfo": {
                    "description": "",
                    "id": "",
                    "next": {"id": "560473", "type": "Track"},
                    "prev": {"id": "88559144", "type": "Track"},
                    "repeatMode": "None",
                    "shuffled": False,
                    "type": "",
                },
                "extra": {},
                "hasNext": True,
                "hasPause": True,
                "hasPlay": False,
                "hasPrev": False,
                "hasProgressBar": True,
                "id": "WZq643oKyW8",
                "liveStreamText": "",
                "playerType": "",
                "playlistDescription": "",
                "playlistId": "",
                "playlistType": "",
                "progress": 1.0,
                "showPlayer": True,
                "subtitle": "www.youtube.com",
                "title": "Би-2 Лучшие песни...",
                "type": "",
            },
            "playing": True,
            "volume": 0.5,
            "local_push": True,
        },
        "extra": {
            "appState": encode_extra(
                {
                    "item": {
                        "thumbnail_url_16x9": "https://avatars.mds.yandex.net/get-vthumb/3824233/731068d602e061926601848918f20342/800x360",
                        "type": "video",
                    }
                }
            )
        },
    }

    device = {"id": "", "name": "", "quasar_info": {"device_id": "", "platform": ""}}
    speaker = YandexStation(FakeQuasar(), device)
    speaker.async_set_state(data)

    assert speaker.media_artist == "www.youtube.com"
    assert speaker.media_content_type == "video"
    assert speaker.media_duration == 5140
    assert (
        speaker.media_image_url
        == "https://avatars.mds.yandex.net/get-vthumb/3824233/731068d602e061926601848918f20342/800x360"
    )
    assert speaker.media_position == 1
    assert speaker.media_title == "Би-2 Лучшие песни..."
    assert speaker.state == "playing"


def _test_kinopoisk():
    data = {
        "state": {
            "aliceState": "IDLE",
            "canStop": True,
            "hdmi": {"capable": True, "present": True},
            "playerState": {
                "duration": 399.0,
                "entityInfo": {
                    "description": "",
                    "id": "",
                    "next": {"id": "560473", "type": "Track"},
                    "prev": {"id": "88559144", "type": "Track"},
                    "repeatMode": "None",
                    "shuffled": False,
                    "type": "",
                },
                "extra": {},
                "hasNext": True,
                "hasPause": True,
                "hasPlay": False,
                "hasPrev": False,
                "hasProgressBar": True,
                "id": "42da7050e62ccfe49f37e67351883058",
                "liveStreamText": "",
                "playerType": "",
                "playlistDescription": "",
                "playlistId": "",
                "playlistType": "",
                "progress": 93.0,
                "showPlayer": True,
                "subtitle": "Смешарики. Новый сезон, 1 сезон, 1 серия",
                "title": "Смешарики. Новый сезон - Сезон 1 - Серия 1 - Природное свойство",
                "type": "",
            },
            "playing": True,
            "volume": 0.5,
            "local_push": True,
        },
        "extra": {
            "appState": encode_extra(
                {
                    "item": {
                        "episode": 1,
                        "genre": "семейный, детский, мультфильм",
                        "season": 1,
                        "thumbnail_url_16x9": "https://avatars.mds.yandex.net/get-vh/3371956/4864628686399976456-osdbSmYti8-SnuEJnOQuRg-1589623034/640x360",
                        "type": "tv_show_episode",
                    }
                }
            )
        },
    }

    device = {"id": "", "name": "", "quasar_info": {"device_id": "", "platform": ""}}
    speaker = YandexStation(FakeQuasar(), device)
    speaker.async_set_state(data)

    assert speaker.media_artist == "Смешарики. Новый сезон, 1 сезон, 1 серия"
    assert speaker.media_content_type == "tvshow"
    assert speaker.media_duration == 399
    assert (
        speaker.media_image_url
        == "https://avatars.mds.yandex.net/get-vh/3371956/4864628686399976456-osdbSmYti8-SnuEJnOQuRg-1589623034/640x360"
    )
    assert speaker.media_position == 93
    assert (
        speaker.media_title
        == "Смешарики. Новый сезон - Сезон 1 - Серия 1 - Природное свойство"
    )
    assert speaker.state == "playing"
