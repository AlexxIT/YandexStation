import asyncio
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)

from . import FakeYandexStation


def _player_frame(*, playing=True, omit=(), **changes):
    player = {
        "duration": 1920.0,
        "entityInfo": {"description": "", "id": "", "type": ""},
        "extra": {},
        "hasNext": False,
        "hasPause": True,
        "hasPlay": False,
        "hasPrev": False,
        "hasProgressBar": True,
        "id": "",
        "liveStreamText": "",
        "playerType": "com.yandex.tv.live",
        "playlistDescription": "",
        "playlistId": "",
        "playlistPuid": "",
        "playlistType": "",
        "progress": 27.0,
        "showPlayer": True,
        "subtitle": "360 Новости — Новости 360",
        "title": "Новости 360",
        "type": "",
    }
    player.update(changes)
    for key in omit:
        player.pop(key)
    return {
        "state": {
            "aliceState": "IDLE",
            "canStop": True,
            "hdmi": {"capable": True, "present": False},
            "playerState": player,
            "playing": playing,
            "volume": 0.2,
        }
    }


@pytest.mark.parametrize(
    "changes,channel",
    [
        ({}, "360 Новости — Новости 360"),
        ({"subtitle": ""}, None),
        ({"subtitle": None, "liveStreamText": None}, None),
        ({"omit": ("liveStreamText",)}, "360 Новости — Новости 360"),
        ({"playerType": "live"}, "360 Новости — Новости 360"),  # Synthetic alias.
    ],
)
def test_yaos_live_tv(changes, channel):
    # Reconstructed envelope using measured modern Live TV markers, not raw capture.
    entity = FakeYandexStation()
    entity.async_set_state(_player_frame(**changes))

    assert entity.media_content_type == MediaType.CHANNEL
    assert entity.media_channel == channel
    assert entity.media_artist is None
    assert entity.media_series_title is None
    assert entity.media_content_id == ""
    assert entity.media_title == "Новости 360"
    assert entity.media_duration == 1920.0
    assert entity.media_position == 27.0
    assert entity.state == MediaPlayerState.PLAYING


@pytest.mark.parametrize(
    "kind,subtitle,duration,title,expected,series",
    [
        ("tv_show_episode", "Смешарики", 390.0, "1. Скамейка",
         MediaType.TVSHOW, "Смешарики"),
        ("movie", "", 6756.0, "Чебурашка", MediaType.MOVIE, None),
    ],
)
def test_yaos_kinopoisk_vod(kind, subtitle, duration, title, expected, series):
    # Reconstructed from J-0193 measured fields; other envelope values are synthetic.
    entity = FakeYandexStation()
    entity.async_set_state(_player_frame(
        type=kind, playerType="com.yandex.tv.videoplayer", subtitle=subtitle,
        duration=duration, title=title, id="synthetic-vod",
    ))

    assert entity.media_content_type == expected
    assert entity.media_series_title == series
    assert entity.media_artist is None
    assert entity.media_channel is None
    assert entity.media_title == title
    assert entity.media_content_id == "synthetic-vod"
    assert entity.media_duration == duration
    assert entity.media_position == 27.0


@pytest.mark.parametrize("backend,continue_video", [
    ("com.yandex.tv.videoplayer", True), ("com.yandex.tv.live", True),
    ("music_thin", False), ("ru.yandex.quasar.app", False),
    ("unknown", False), (None, False),
])
def test_media_play_resumes_selected_player(backend, continue_video):
    async def scenario():
        entity = FakeYandexStation()
        entity.glagol = AsyncMock()
        entity.async_set_state(_player_frame(
            playing=False, playerType=backend, type="tv_show_episode",
            omit=("playerType",) if backend is None else (),
        ))
        if continue_video:
            entity.async_set_state(_player_frame(
                playing=False, playerType="music_thin", type="Track",
            ))
        await entity.async_media_play()
        if continue_video:
            entity.glagol.send.assert_awaited_once_with({
                "command": "serverAction",
                "serverActionEventPayload": {
                    "type": "server_action", "name": "update_form",
                    "payload": {
                        "form_update": {
                            "name": "personal_assistant.scenarios.player_continue",
                            "slots": [],
                        },
                        "resubmit": True,
                    },
                },
            })
            entity.async_set_state(_player_frame(playerType="music_thin", type="Track"))
            entity.async_set_state(_player_frame(
                playing=False, playerType="music_thin", type="Track",
            ))
            await entity.async_media_play()
            entity.glagol.send.assert_awaited_with({"command": "play"})
        else:
            entity.glagol.send.assert_awaited_once_with({"command": "play"})
        assert entity.state == MediaPlayerState.PAUSED

    asyncio.run(scenario())


@pytest.mark.parametrize("backend", ["com.yandex.tv.videoplayer", "com.yandex.tv.live"])
@pytest.mark.parametrize("playing", [True, False])
def test_glagol_background_music_keeps_video_and_updates_device(backend, playing):
    entity = FakeYandexStation()
    video = _player_frame(
        playerType=backend, type="tv_show_episode", id="synthetic-video",
        title="1. Скамейка", subtitle="Смешарики",
        extra={"coverURI": "https://example.invalid/cover.jpg"},
        playlistType="Playlist", hasNext=True,
        entityInfo={"repeatMode": "All", "shuffled": True},
    )
    video["state"]["playing"] = playing
    entity.async_set_state(video)
    assert entity.state == (MediaPlayerState.PLAYING if playing else MediaPlayerState.PAUSED)
    fields = (
        "state", "media_title", "media_content_type", "media_content_id",
        "media_artist", "media_channel", "media_series_title", "media_duration",
        "media_position", "media_position_updated_at", "media_image_url",
        "media_playlist", "repeat", "shuffle", "supported_features",
    )
    selected = tuple(getattr(entity, key) for key in fields)
    for volume in (0.8, 0.0):
        background = _player_frame(
            playerType="music_thin", type="Track", title="Другой трек",
            showPlayer=True, progress=0.0,
        )
        background["state"].update(playing=False, volume=volume, aliceState="LISTENING")
        entity.async_set_state(background)
        assert tuple(getattr(entity, key) for key in fields) == selected
        assert entity.volume_level == 0.8
        assert entity.is_volume_muted is (volume == 0.0)
        assert entity.extra_state_attributes["alice_state"] == "LISTENING"


@pytest.mark.parametrize("playing", [True, False])
def test_glagol_video_cleanup_respects_selected_music(playing):
    entity = FakeYandexStation()
    video = dict(playerType="com.yandex.tv.videoplayer", type="tv_show_episode")
    clear = dict(
        playing=False, playerType="", type="", id="", title="", subtitle="",
        showPlayer=False, duration=0.0, progress=0.0,
    )
    entity.async_set_state(_player_frame(playing=False, **video))
    entity.async_set_state(_player_frame(**clear))
    assert entity.state == MediaPlayerState.IDLE
    assert entity.media_title is None
    assert entity.media_content_type is None

    entity.async_set_state(_player_frame(**video))
    music = dict(playerType="music_thin", type="Track", title="Музыка", showPlayer=True)
    entity.async_set_state(_player_frame(**music))
    entity.async_set_state(_player_frame(playing=playing, **music))
    position_time = entity.media_position_updated_at
    entity.async_set_state(_player_frame(**clear))
    assert entity.state == (MediaPlayerState.PLAYING if playing else MediaPlayerState.PAUSED)
    assert entity.media_content_type == MediaType.MUSIC
    assert entity.media_title == "Музыка"
    assert entity.media_position_updated_at == position_time
    # Once the screen has closed, cleanup is no longer a delayed video teardown.
    entity.async_set_state(_player_frame(**clear))
    assert entity.state == MediaPlayerState.IDLE
    assert entity.media_title is None
    assert entity.media_position is None


@pytest.mark.parametrize(
    "backend,show",
    [
        ("com.yandex.tv.videoplayer", False),
        ("com.yandex.tv.videoplayer", None),
        ("com.yandex.tv.videoplayer", "absent"),
        ("ru.yandex.quasar.app", True),
        ("unknown", True),
    ],
)
def test_glagol_unconfirmed_background_is_not_blocked(backend, show):
    entity = FakeYandexStation()
    entity.async_set_state(_player_frame(playerType=backend, type="movie"))
    entity.async_set_state(_player_frame(
        playing=False, playerType="music_thin", type="Track", showPlayer=show,
        omit=("showPlayer",) if show == "absent" else (),
    ))
    assert entity.state == MediaPlayerState.PAUSED
    assert entity.media_content_type == MediaType.MUSIC


@pytest.mark.parametrize(
    "current,incoming",
    [(None, "music_thin"), ("", "music_thin"),
     ("com.yandex.tv.videoplayer", None), ("com.yandex.tv.videoplayer", "")],
)
def test_glagol_pause_without_player_identity(current, incoming):
    entity = FakeYandexStation()
    entity.async_set_state(_player_frame(playerType=current, type="movie"))
    paused = _player_frame(playerType=incoming, type="Track", title="Другой трек")
    paused["state"]["playing"] = False
    entity.async_set_state(paused)
    assert entity.state == MediaPlayerState.PAUSED
    assert entity.media_title == "Другой трек"


@pytest.mark.parametrize(
    "changes,live_text,expected",
    [
        ({"type": "Track"}, "Прямой эфир", MediaType.MUSIC),
        ({"type": "FmRadio"}, "Прямой эфир", "radio"),
        ({"type": "movie"}, "", MediaType.CHANNEL),
        ({"type": "video", "playerType": "live"}, "", MediaType.CHANNEL),
        ({"type": "movie", "playerType": "unknown"}, "Прямой эфир", MediaType.CHANNEL),
        ({"type": "video", "playerType": "unknown"}, "Прямой эфир", MediaType.CHANNEL),
        ({"type": "tv_show_episode", "playerType": "unknown"},
         "Прямой эфир", MediaType.CHANNEL),
        ({"playerType": "com.yandex.tv.videoplayer"}, "", MediaType.VIDEO),
        ({"playerType": "com.yandex.tv.videoplayer", "subtitle": ""}, "", MediaType.VIDEO),
        ({"playerType": "ru.yandex.quasar.app"}, "", MediaType.VIDEO),
        ({"playerType": "ru.yandex.quasar.app", "subtitle": ""}, "", MediaType.VIDEO),
        ({"type": "unrecognized", "playerType": "unknown"}, "", None),
    ],
)
def test_video_classification_priority(changes, live_text, expected):
    # Synthetic conflicts: audio beats live; either live marker beats VOD.
    frame = _player_frame(**{
        "subtitle": "Подпись", "liveStreamText": live_text, **changes,
    })
    entity = FakeYandexStation()
    entity.async_set_state(frame)

    assert entity.media_content_type == expected
    assert entity.media_artist == ("Подпись" if expected == MediaType.MUSIC else None)
    assert entity.media_channel == ("Подпись" if expected == MediaType.CHANNEL else None)
    assert entity.media_series_title == (
        "Подпись" if expected == MediaType.TVSHOW else None
    )


@pytest.mark.parametrize("mode", ["absent", "null", "empty"])
@pytest.mark.parametrize(
    "signal,expected",
    [
        ({"type": "Track"}, MediaType.MUSIC),
        ({"type": "FmRadio"}, "radio"),
        ({"type": "movie"}, MediaType.MOVIE),
        ({"type": "tv_show_episode"}, MediaType.TVSHOW),
        ({"type": "video"}, MediaType.VIDEO),
        ({"playerType": "com.yandex.tv.live"}, MediaType.CHANNEL),
        ({"liveStreamText": "Прямой эфир"}, MediaType.CHANNEL),
        ({"playerType": "com.yandex.tv.videoplayer"}, MediaType.VIDEO),
        ({}, None),
    ],
)
def test_classification_optional_fields(mode, signal, expected):
    # Missing/null/empty optional markers do not mask the remaining positive signal.
    optional = ("type", "playerType", "liveStreamText", "subtitle")
    changes = dict.fromkeys(optional, None if mode == "null" else "")
    changes.update(signal)
    omitted = tuple(key for key in optional if key not in signal)
    entity = FakeYandexStation()
    entity.async_set_state(_player_frame(
        omit=omitted if mode == "absent" else (), **changes,
    ))

    assert entity.media_content_type == expected
    assert entity.media_artist is None
    assert entity.media_channel is None
    assert entity.media_series_title is None
    assert entity.media_title == "Новости 360"


def test_content_type_transitions_reset_metadata(monkeypatch):
    entity = FakeYandexStation()
    # Cloud fallback publishes unconditionally; this seam has no HA instance.
    monkeypatch.setattr(entity, "async_write_ha_state", lambda: None)
    for changes, expected, metadata in [
        ({"playerType": "com.yandex.tv.live"}, MediaType.CHANNEL,
         (None, "Подпись", None)),
        ({"type": "Track"}, MediaType.MUSIC, ("Подпись", None, None)),
        ({"type": "FmRadio"}, "radio", (None, None, None)),
        ({"type": "tv_show_episode"}, MediaType.TVSHOW, (None, None, "Подпись")),
        ({"type": "movie"}, MediaType.MOVIE, (None, None, None)),
        ({"type": "video"}, MediaType.VIDEO, (None, None, None)),
        ({"type": "unknown"}, None, (None, None, None)),
    ]:
        # Every update owns a fresh envelope; never mutate retained local_state.
        entity.async_set_state(_player_frame(**{
            "playerType": "unknown", "subtitle": "Подпись",
            "id": "synthetic-content", "playlistType": "Playlist",
            "extra": {"coverURI": "https://example.invalid/cover.jpg"},
            "entityInfo": {"type": "Playlist", "repeatMode": "All", "shuffled": True},
            **changes,
        }))
        assert entity.media_content_type == expected
        assert (entity.media_artist, entity.media_channel,
                entity.media_series_title) == metadata
        assert entity.media_playlist == MediaType.PLAYLIST
        assert entity.repeat == RepeatMode.ALL
        assert entity.shuffle is True
        assert entity.media_image_url == "https://example.invalid/cover.jpg"

    entity.async_set_state(_player_frame(
        type="movie", playerType="com.yandex.tv.videoplayer",
    ))
    idle = _player_frame()
    del idle["state"]["playerState"]
    idle["state"]["playing"] = False
    entity.async_set_state(idle)
    assert entity.state == MediaPlayerState.IDLE
    assert entity.assumed_state is False
    for cloud in (False, True):
        if cloud:
            entity.async_set_state(None)
        assert entity.assumed_state is cloud
        assert entity.media_content_type is None
        assert entity.media_artist is None
        assert entity.media_channel is None
        assert entity.media_series_title is None
        assert entity.media_title is None
        assert entity.media_content_id is None
        assert entity.media_duration is None
        assert entity.media_position is None
        assert entity.media_position_updated_at is None
        assert entity.media_image_url is None
        assert entity.media_playlist is None
        assert entity.repeat is None
        assert entity.shuffle is None


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
        | MediaPlayerEntityFeature.STOP
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
    assert entity.media_content_type == MediaType.VIDEO
    assert entity.media_series_title is None
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
    assert entity.media_content_type == MediaType.VIDEO
    assert entity.media_series_title is None
    assert entity.shuffle is None
