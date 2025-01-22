from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)

from . import FakeYandexStation


def test_idle():
    state = {
        "aliceState": "IDLE",
        "canStop": False,
        "hdmi": {"capable": False, "present": False},
        "playing": False,
        "timeSinceLastVoiceActivity": 509,
        "volume": 0.2,
    }

    entity = FakeYandexStation()
    entity.async_set_state({"state": state})

    assert entity.assumed_state is False
    assert entity.extra_state_attributes == {"alice_state": "IDLE"}
    assert entity.media_content_id is None
    assert entity.state == MediaPlayerState.IDLE
    assert entity.volume_level == 0.2


def test_track():
    state = {
        "aliceState": "IDLE",
        "canStop": True,
        "hdmi": {"capable": False, "present": False},
        "playerState": {
            "duration": 288.0,
            "entityInfo": {
                "description": "",
                "id": "37232253",
                "next": {"id": "", "type": "Track"},
                "prev": {"id": "114930031", "type": "Track"},
                "repeatMode": "None",
                "type": "Track",
            },
            "extra": {
                "coverURI": "avatars.yandex.net/get-music-content/49876/a4be9993.a.4712278-1/%%",
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
            "playlistId": "xxx",
            "playlistPuid": "xxx",
            "playlistType": "Track",
            "progress": 244.86800000000002,
            "showPlayer": False,
            "subtitle": "Би-2",
            "title": "Пора возвращаться домой",
            "type": "Track",
        },
        "playing": True,
        "timeSinceLastVoiceActivity": 255,
        "volume": 0.4,
    }

    entity = FakeYandexStation()
    entity.async_set_state({"state": state})

    assert entity.assumed_state is False
    assert entity.extra_state_attributes == {"alice_state": "IDLE"}
    assert entity.media_artist == "Би-2"
    assert entity.media_content_id == "37232253"
    assert entity.media_content_type == MediaType.MUSIC
    assert entity.media_duration == 288.0
    assert entity.media_playlist == MediaType.TRACK
    assert entity.media_position == 244.86800000000002
    assert entity.media_title == "Пора возвращаться домой"
    assert entity.repeat == RepeatMode.OFF
    assert entity.shuffle is None
    assert entity.state == MediaPlayerState.PLAYING
    assert entity.volume_level == 0.4

    assert (
        entity.supported_features
        == MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.SHUFFLE_SET
        | MediaPlayerEntityFeature.REPEAT_SET
    )


def test_reapeat():
    state = {
        "aliceState": "IDLE",
        "canStop": True,
        "hdmi": {"capable": False, "present": False},
        "playerState": {
            "duration": 237.0,
            "entityInfo": {
                "description": "",
                "id": "2192815",
                "next": {"id": "", "type": "Track"},
                "prev": {"id": "2192815", "type": "Track"},
                "repeatMode": "One",
                "type": "Track",
            },
            "extra": {
                "coverURI": "avatars.yandex.net/get-music-content/32236/8bd0edef.a.217021-1/%%",
                "stateType": "music",
            },
            "hasNext": True,
            "hasPause": True,
            "hasPlay": False,
            "hasPrev": True,
            "hasProgressBar": True,
            "id": "2192815",
            "liveStreamText": "",
            "playerType": "music_thin",
            "playlistDescription": "",
            "playlistId": "2192815",
            "playlistPuid": "xxx",
            "playlistType": "Track",
            "progress": 3.545,
            "showPlayer": False,
            "subtitle": "Мумий Тролль",
            "title": "Доля риска",
            "type": "Track",
        },
        "playing": True,
        "volume": 0.0,
    }

    entity = FakeYandexStation()
    entity.async_set_state({"state": state})

    assert entity.repeat == RepeatMode.ONE


def test_artist():
    state = {
        "aliceState": "IDLE",
        "canStop": True,
        "hdmi": {"capable": False, "present": False},
        "playerState": {
            "duration": 173.0,
            "entityInfo": {
                "description": "",
                "id": "160970",
                "next": {"id": "113351163", "type": "Track"},
                "prev": {"id": "123541455", "type": "Track"},
                "repeatMode": "None",
                "shuffled": False,
                "type": "Artist",
            },
            "extra": {
                "coverURI": "avatars.yandex.net/get-music-content/8871869/b35dc4aa.a.25433372-1/%%",
                "stateType": "music",
            },
            "hasNext": True,
            "hasPause": True,
            "hasPlay": False,
            "hasPrev": True,
            "hasProgressBar": True,
            "id": "40053606",
            "liveStreamText": "",
            "playerType": "music_thin",
            "playlistDescription": "",
            "playlistId": "160970",
            "playlistPuid": "xxx",
            "playlistType": "Artist",
            "progress": 120.209,
            "showPlayer": False,
            "subtitle": "Noize MC",
            "title": "Песня для радио",
            "type": "Track",
        },
        "playing": True,
        "volume": 0.0,
    }

    entity = FakeYandexStation()
    entity.async_set_state({"state": state})

    assert entity.media_content_id == "40053606"
    assert entity.media_content_type == MediaType.MUSIC
    assert entity.media_playlist == MediaType.ARTIST
    assert entity.repeat == RepeatMode.OFF
    assert entity.shuffle is False


def test_album():
    state = {
        "aliceState": "IDLE",
        "canStop": True,
        "hdmi": {"capable": False, "present": False},
        "playerState": {
            "duration": 303.0,
            "entityInfo": {
                "description": "",
                "id": "10030",
                "next": {"id": "38634573", "type": "Track"},
                "prev": {"id": "93916267", "type": "Track"},
                "repeatMode": "All",
                "shuffled": False,
                "type": "Album",
            },
            "extra": {
                "coverURI": "avatars.yandex.net/get-music-content/5853241/bc8002a7.a.10030-10/%%",
                "stateType": "music",
            },
            "hasNext": True,
            "hasPause": True,
            "hasPlay": False,
            "hasPrev": True,
            "hasProgressBar": True,
            "id": "38634572",
            "liveStreamText": "",
            "playerType": "music_thin",
            "playlistDescription": "",
            "playlistId": "10030",
            "playlistPuid": "xxx",
            "playlistType": "Album",
            "progress": 5.573,
            "showPlayer": False,
            "subtitle": "КИНО",
            "title": "Песня без слов",
            "type": "Track",
        },
        "playing": True,
        "volume": 0.0,
    }

    entity = FakeYandexStation()
    entity.async_set_state({"state": state})

    assert entity.media_content_id == "38634572"
    assert entity.media_content_type == MediaType.MUSIC
    assert entity.media_playlist == MediaType.ALBUM
    assert entity.repeat == RepeatMode.ALL
    assert entity.shuffle is False


def test_radio():
    state = {
        "aliceState": "IDLE",
        "canStop": True,
        "hdmi": {"capable": False, "present": False},
        "playerState": {
            "duration": 0.0,
            "entityInfo": {
                "description": "",
                "id": "nashe",
                "next": {"id": "", "type": "Track"},
                "prev": {"id": "nashe", "type": "Track"},
                "repeatMode": "None",
                "shuffled": False,
                "type": "FmRadio",
            },
            "extra": {
                "coverURI": "avatars.mds.yandex.net/get-music-misc/49997/nashe-225-full/%%",
                "stateType": "music",
            },
            "hasNext": True,
            "hasPause": True,
            "hasPlay": False,
            "hasPrev": True,
            "hasProgressBar": True,
            "id": "nashe",
            "liveStreamText": "",
            "playerType": "music_thin",
            "playlistDescription": "",
            "playlistId": "nashe",
            "playlistPuid": "xxx",
            "playlistType": "FmRadio",
            "progress": 38.224999999999994,
            "showPlayer": False,
            "subtitle": "",
            "title": "Наше радио",
            "type": "FmRadio",
        },
        "playing": True,
        "timeSinceLastVoiceActivity": 43,
        "volume": 0.4,
    }

    entity = FakeYandexStation()
    entity.async_set_state({"state": state})

    assert entity.media_artist is None
    assert entity.media_content_id == "nashe"
    assert entity.media_content_type == "radio"
    assert entity.media_duration is None
    assert entity.media_playlist == "radio"
    assert entity.media_title == "Наше радио"
    assert entity.shuffle is False


def test_podcast():
    state = {
        "aliceState": "IDLE",
        "canStop": True,
        "hdmi": {"capable": False, "present": False},
        "playerState": {
            "duration": 3280.0,
            "entityInfo": {
                "description": "",
                "id": "414787002:1104",
                "next": {"id": "124568952", "type": "Track"},
                "prev": {"id": "nashe", "type": "Track"},
                "repeatMode": "None",
                "shuffled": False,
                "type": "Playlist",
            },
            "extra": {
                "coverURI": "avatars.yandex.net/get-music-content/6386858/4c45b886.t.124374440-1/%%",
                "stateType": "music",
            },
            "hasNext": True,
            "hasPause": True,
            "hasPlay": False,
            "hasPrev": True,
            "hasProgressBar": True,
            "id": "124374440",
            "liveStreamText": "",
            "playerType": "music_thin",
            "playlistDescription": "",
            "playlistId": "414787002:1104",
            "playlistPuid": "xxx",
            "playlistType": "Playlist",
            "progress": 36.259,
            "showPlayer": False,
            "subtitle": "MINAEV LIVE",
            "title": "Гагарин / Как один полет изменил весь мир / Личности / МИНАЕВ",
            "type": "Track",
        },
        "playing": True,
        "timeSinceLastVoiceActivity": 42,
        "volume": 0.4,
    }

    entity = FakeYandexStation()
    entity.async_set_state({"state": state})

    assert entity.media_content_id == "124374440"
    assert entity.media_content_type == MediaType.MUSIC
    assert entity.media_playlist == MediaType.PLAYLIST
    assert entity.shuffle is False


def test_tv():
    state = {
        "aliceState": "LISTENING",
        "canStop": True,
        "hdmi": {"capable": True, "present": False},
        "playerState": {
            "duration": 0.0,
            "entityInfo": {"description": "", "id": "", "type": ""},
            "extra": {},
            "hasNext": False,
            "hasPause": True,
            "hasPlay": False,
            "hasPrev": False,
            "hasProgressBar": False,
            "id": "49128833ca298c65b565d5d93761e759",
            "liveStreamText": "Прямой эфир",
            "playerType": "ru.yandex.quasar.app",
            "playlistDescription": "",
            "playlistId": "",
            "playlistPuid": "",
            "playlistType": "",
            "progress": 0.0,
            "showPlayer": True,
            "subtitle": "360 Новости — Новости 360",
            "title": "Новости 360",
            "type": "",
        },
        "playing": True,
        "volume": 0.2,
    }

    entity = FakeYandexStation()
    entity.async_set_state({"state": state})

    assert entity.media_artist is None
    assert entity.media_content_id == "49128833ca298c65b565d5d93761e759"
    assert entity.media_content_type == MediaType.CHANNEL
    assert entity.media_channel == "360 Новости — Новости 360"
    assert entity.shuffle is None


def test_video():
    state = {
        "aliceState": "IDLE",
        "canStop": True,
        "hdmi": {"capable": True, "present": False},
        "playerState": {
            "duration": 351.0,
            "entityInfo": {"description": "", "id": "", "type": ""},
            "extra": {},
            "hasNext": True,
            "hasPause": True,
            "hasPlay": False,
            "hasPrev": False,
            "hasProgressBar": True,
            "id": "4e0a11ba3b549da0b7291235f8a50c2e",
            "liveStreamText": "",
            "playerType": "ru.yandex.quasar.app",
            "playlistDescription": "",
            "playlistId": "",
            "playlistPuid": "",
            "playlistType": "",
            "progress": 27.0,
            "showPlayer": True,
            "subtitle": "Фиксики, 1 сезон, 1 серия",
            "title": "Фиксики - Сезон 1 - Серия 1 - Сифон",
            "type": "",
        },
        "playing": True,
        "timeSinceLastVoiceActivity": 33,
        "volume": 0.2,
    }

    entity = FakeYandexStation()
    entity.async_set_state({"state": state})

    assert entity.media_artist is None
    assert entity.media_content_id == "4e0a11ba3b549da0b7291235f8a50c2e"
    assert entity.media_content_type == MediaType.TVSHOW
    assert entity.media_series_title == "Фиксики, 1 сезон, 1 серия"
    assert entity.shuffle is None


def test_movie():
    state = {
        "aliceState": "IDLE",
        "canStop": True,
        "hdmi": {"capable": True, "present": False},
        "playerState": {
            "duration": 7950.0,
            "entityInfo": {"description": "", "id": "", "type": ""},
            "extra": {},
            "hasNext": False,
            "hasPause": True,
            "hasPlay": False,
            "hasPrev": False,
            "hasProgressBar": True,
            "id": "402f8e529e4e7a31b3b43f4383cbc10d",
            "liveStreamText": "",
            "playerType": "ru.yandex.quasar.app",
            "playlistDescription": "",
            "playlistId": "",
            "playlistPuid": "",
            "playlistType": "",
            "progress": 15.0,
            "showPlayer": True,
            "subtitle": "военный, боевик, история, биография, 18+, 2019",
            "title": "Мидуэй",
            "type": "",
        },
        "playing": True,
        "volume": 0.2,
    }

    entity = FakeYandexStation()
    entity.async_set_state({"state": state})

    assert entity.media_artist is None
    assert entity.media_content_id == "402f8e529e4e7a31b3b43f4383cbc10d"
    assert entity.media_content_type == MediaType.TVSHOW
    assert entity.media_series_title == "военный, боевик, история, биография, 18+, 2019"
    assert entity.shuffle is None
