import asyncio
import base64
import json
import time

from homeassistant.components.media_player import MediaPlayerState

from custom_components.yandex_station.core import stream, utils
from custom_components.yandex_station.core import yandex_station

from . import FakeYandexStation

STREAM_URL = "http://192.168.1.123:8123/test.mp3"


class FakeGlagol:
    def __init__(self):
        self.sent: list[dict] = []

    async def send(self, payload: dict):
        self.sent.append(payload)


def decode(payload: dict) -> tuple[str, dict]:
    """externalCommandBypass => (directive name, directive payload)."""
    assert payload["command"] == "externalCommandBypass"

    raw = base64.b64decode(payload["data"])
    fields, pos = {}, 0
    while pos < len(raw):
        tag, wire = raw[pos] >> 3, raw[pos] & 0b111
        assert wire == 2, wire  # both fields are LEN-delimited strings
        pos += 1

        size = shift = 0
        while True:
            byte = raw[pos]
            pos += 1
            size |= (byte & 0x7F) << shift
            if not byte & 0x80:
                break
            shift += 7

        fields[tag] = raw[pos : pos + size].decode()
        pos += size

    return fields[1], json.loads(fields[2])


def setup_module():
    # get_stream_url wraps every link in the HA proxy view
    stream.StreamView.hass_url = "http://192.168.1.123:8123"
    stream.StreamView.key = "test"


def test_radio_play():
    """Legacy directive for stations without the audio client."""
    payload = utils.get_stream_url(STREAM_URL, "music")
    name, data = decode(payload)

    assert name == "radio_play"
    assert data["force_restart_player"] is True
    assert ".mp3" in data["streamUrl"]


def test_audio_play():
    """Station firmware since ~2026.07 ignores radio_play params."""
    payload = utils.get_stream_url(STREAM_URL, "music", audio_client=True)
    name, data = decode(payload)

    assert name == "audio_play"
    # format is required - without it the station drops the directive
    assert data["stream"]["format"] == "MP3"
    assert data["stream"]["type"] == "Track"
    assert data["stream"]["offset_ms"] == 0
    assert ".mp3" in data["stream"]["url"]
    assert data["set_pause"] is False
    assert "metadata" not in data


def test_audio_play_hls():
    payload = utils.get_stream_url(
        "http://192.168.1.123:8123/playlist.m3u8", "music", audio_client=True
    )
    name, data = decode(payload)

    assert name == "audio_play"
    assert data["stream"]["format"] == "HLS"
    assert data["stream"]["type"] == "FmRadio"


def test_audio_play_metadata():
    metadata = {
        "title": "Title",
        "subtitle": "Artist",
        "imageUrl": "https://avatars.mds.yandex.net/cover/%%",
    }
    payload = utils.get_stream_url(STREAM_URL, "music", metadata, audio_client=True)
    name, data = decode(payload)

    assert data["metadata"]["title"] == "Title"
    assert data["metadata"]["subtitle"] == "Artist"
    # station returns it back as a schemeless coverURI
    assert data["metadata"]["art_image_url"] == "avatars.mds.yandex.net/cover/%%"


def test_audio_client_support():
    """Stations report supported features in every local message."""
    entity = FakeYandexStation()
    assert entity.audio_client is False

    entity.async_set_state(
        {
            "state": {"aliceState": "IDLE", "playing": False, "volume": 0.2},
            "supported_features": ["audio_client", "audio_client_hls", "multiroom"],
        }
    )
    assert entity.audio_client is True


def track_state(**overrides) -> dict:
    player_state = {
        "duration": 288.0,
        "entityInfo": {
            "description": "",
            "id": "37232253",
            "next": {"id": "", "type": "Track"},
            "prev": {"id": "114930031", "type": "Track"},
            "repeatMode": "None",
            "type": "Track",
        },
        "extra": {"stateType": "music"},
        "hasNext": True,
        "hasPause": True,
        "hasPlay": False,
        "hasPrev": True,
        "hasProgressBar": True,
        "id": "STATION_OWN_ID",
        "liveStreamText": "",
        "playerType": "music_thin",
        "playlistDescription": "",
        "playlistId": "xxx",
        "playlistPuid": "xxx",
        "playlistType": "Track",
        "progress": 1.0,
        "showPlayer": False,
        "subtitle": "",
        "title": "Local track",
        "type": "Track",
    }
    player_state.update(overrides)
    return {
        "aliceState": "IDLE",
        "canStop": True,
        "hdmi": {"capable": False, "present": False},
        "playerState": player_state,
        "playing": True,
        "volume": 0.4,
    }


def test_pushed_media_id_echoed_as_content_id():
    """A URL pushed via audio_play/radio_play is echoed back as media_content_id.

    Music Assistant's `hass_players` provider trusts this URL match to know it
    still owns the stream, and keeps routing next/prev through its own queue
    instead of forwarding a raw "next"/"prev" straight to the station, which
    would resolve it against the station's own Yandex Music context - not our
    locally pushed playlist.
    """
    entity = FakeYandexStation()
    entity._pushed_media_id = "http://mass.local/stream/abc.mp3"

    entity.async_set_state({"state": track_state()})

    assert entity.media_content_id == "http://mass.local/stream/abc.mp3"


def test_real_track_uses_station_id_when_nothing_pushed():
    """Real Yandex Music playback (voice/app) keeps the station's own id."""
    entity = FakeYandexStation()

    entity.async_set_state({"state": track_state()})

    assert entity.media_content_id == "STATION_OWN_ID"


def test_pushed_media_id_cleared_on_idle():
    """The pushed-URL attribution must not leak into the next, unrelated session."""
    entity = FakeYandexStation()
    entity._pushed_media_id = "http://mass.local/stream/abc.mp3"

    entity.async_set_state(
        {"state": {"aliceState": "IDLE", "playing": False, "volume": 0.2}}
    )

    assert entity._pushed_media_id is None
    assert entity.media_content_id is None


def test_pushed_media_id_kept_while_title_matches():
    """The echoed title matching what we pushed confirms it's still our stream."""
    entity = FakeYandexStation()
    entity._pushed_media_id = "http://mass.local/stream/abc.mp3"
    entity._pushed_media_title = "Local track"

    entity.async_set_state({"state": track_state(title="Local track")})

    assert entity.media_content_id == "http://mass.local/stream/abc.mp3"
    assert entity._pushed_media_confirmed is True


def test_pushed_media_id_survives_stale_echo_right_after_push():
    """Right after we push, the station may still report the previous track for
    a beat before it catches up (e.g. re-starting the local playlist right after
    a voice takeover). That transient mismatch must not be mistaken for a real
    takeover - it would misreport ownership to Music Assistant for content that
    is, in fact, correctly about to play what we just pushed.
    """
    entity = FakeYandexStation()
    entity._pushed_media_id = "http://mass.local/stream/abc.mp3"
    entity._pushed_media_title = "Local track"
    # never confirmed yet - this is the very first update since the push

    entity.async_set_state(
        {"state": track_state(title="Previous cloud track", id="999")}
    )

    assert entity._pushed_media_id == "http://mass.local/stream/abc.mp3"
    assert entity._pushed_media_confirmed is False
    # still optimistically trusted, not yet fallen back to the stale station id
    assert entity.media_content_id == "http://mass.local/stream/abc.mp3"

    # the station catches up on the next update
    entity.async_set_state({"state": track_state(title="Local track")})

    assert entity._pushed_media_confirmed is True
    assert entity.media_content_id == "http://mass.local/stream/abc.mp3"


def test_pushed_media_id_cleared_on_voice_takeover():
    """Voice/app playback (Алиса, включи ...) never passes through IDLE, so a
    title mismatch is the only signal that our push is no longer playing -
    but only once we've actually seen it confirmed at least once, otherwise
    it's indistinguishable from the station still catching up on our push.
    """
    entity = FakeYandexStation()
    entity._pushed_media_id = "http://mass.local/stream/abc.mp3"
    entity._pushed_media_title = "Local track"

    # confirm our push actually took effect first
    entity.async_set_state({"state": track_state(title="Local track")})
    assert entity._pushed_media_confirmed is True

    # then something else takes over
    entity.async_set_state(
        {"state": track_state(title="Some real Yandex Music track", id="123456")}
    )

    assert entity._pushed_media_id is None
    assert entity._pushed_media_title is None
    assert entity._pushed_media_confirmed is False
    assert entity.media_content_id == "123456"


def test_resume_replays_local_push_instead_of_native_play():
    """The station's native "play" resumes its own last real Yandex Music
    (cloud) session, not our externally pushed URL - so resuming our own
    paused local content must re-send our push instead of that bare command.
    """
    entity = FakeYandexStation()
    entity.local_state = {"aliceState": "IDLE", "playing": False}
    entity.glagol = FakeGlagol()
    entity._last_local_media_id = STREAM_URL
    entity._last_local_media_type = "music"

    asyncio.run(entity.async_media_play())

    assert len(entity.glagol.sent) == 1
    name, data = decode(entity.glagol.sent[0])
    assert name == "radio_play"
    assert ".mp3" in data["streamUrl"]


def test_resume_rebuilds_a_fresh_payload_not_a_stale_replay(monkeypatch):
    """Regression: the station silently ignores an audio_play/radio_play
    directive that is byte-for-byte identical to one it already received -
    no new request ever reaches the proxy for it. Caching and re-sending the
    exact original payload was therefore a no-op on a second resume;
    get_stream_url() must be called again so each resume signs a fresh URL
    (the proxy token embeds an "exp" timestamp, which is what makes two
    otherwise-identical resumes produce different bytes on the wire).
    """
    entity = FakeYandexStation()
    entity.local_state = {"aliceState": "IDLE", "playing": False}
    entity.glagol = FakeGlagol()
    entity._last_local_media_id = STREAM_URL
    entity._last_local_media_type = "music"

    real_time = time.time
    monkeypatch.setattr(stream.time, "time", lambda: real_time() + 1)
    asyncio.run(entity.async_media_play())
    monkeypatch.setattr(stream.time, "time", lambda: real_time() + 2)
    asyncio.run(entity.async_media_play())

    assert len(entity.glagol.sent) == 2
    assert entity.glagol.sent[0] != entity.glagol.sent[1]


def test_resume_replays_local_push_after_pause_cleared_pushed_media_id():
    """Regression: pausing our push (glagol "stop") drops the station's
    playerState entirely, same as genuine idle - which already clears
    _pushed_media_id (it governs whether we still echo ownership to MA).
    Resume must not additionally require _pushed_media_id, only the cached
    local-push inputs need to survive a pause, or resume silently falls back
    to the broken native "play" every time.
    """
    entity = FakeYandexStation()
    entity.local_state = {"aliceState": "IDLE", "playing": True}
    entity.glagol = FakeGlagol()
    entity._pushed_media_id = "http://mass.local/stream/abc.mp3"
    entity._pushed_media_title = "Local track"
    entity._last_local_media_id = STREAM_URL
    entity._last_local_media_type = "music"

    # pausing (glagol "stop") - the station reports no playerState at all
    entity.async_set_state(
        {"state": {"aliceState": "IDLE", "playing": False, "volume": 0.2}}
    )
    assert entity._pushed_media_id is None
    assert entity._last_local_media_id == STREAM_URL  # must survive the pause

    asyncio.run(entity.async_media_play())

    assert len(entity.glagol.sent) == 1
    name, _ = decode(entity.glagol.sent[0])
    assert name == "radio_play"


def test_resume_uses_native_play_without_a_local_push():
    """Nothing of ours was pushed (or a voice takeover was detected) - the
    native command is correct here, it resumes real Yandex Music playback.
    """
    entity = FakeYandexStation()
    entity.local_state = {"aliceState": "IDLE", "playing": False}
    entity.glagol = FakeGlagol()

    asyncio.run(entity.async_media_play())

    assert entity.glagol.sent == [{"command": "play"}]


def test_pause_reports_idle_immediately_for_local_content(monkeypatch):
    """Regression: Music Assistant's own resume only rebuilds a fresh,
    position-accurate stream (player_queues/controller.py's _handle_play)
    once it sees the queue leave PAUSED - while we still show paused, it
    instead forwards a bare native "play", which for local content replays
    our last push from the start (see async_media_play), losing position.
    This used to be worked around with a 32s delayed idle-flip on the
    (wrong) theory that only long pauses were affected - in fact every
    resume attempted while we still show paused hits this, regardless of
    pause duration, so we now report idle immediately instead of waiting.
    """
    entity = FakeYandexStation()
    entity.local_state = {"aliceState": "IDLE", "playing": True}
    entity.glagol = FakeGlagol()
    entity._last_local_media_id = STREAM_URL
    write_calls = []
    monkeypatch.setattr(entity, "async_write_ha_state", lambda: write_calls.append(1))

    asyncio.run(entity.async_media_pause())

    assert entity.glagol.sent == [{"command": "stop"}]
    assert entity._attr_state == MediaPlayerState.IDLE
    assert write_calls == [1]


def test_pause_does_not_force_idle_without_local_content(monkeypatch):
    """Real Yandex Music (voice/app) playback has a genuine native pause -
    there's no rebuild-on-resume fallback here to protect.
    """
    entity = FakeYandexStation()
    entity.local_state = {"aliceState": "IDLE", "playing": True}
    entity.glagol = FakeGlagol()
    write_calls = []
    monkeypatch.setattr(entity, "async_write_ha_state", lambda: write_calls.append(1))

    asyncio.run(entity.async_media_pause())

    assert entity.glagol.sent == [{"command": "stop"}]
    assert write_calls == []


def test_set_state_reports_idle_not_paused_for_local_content():
    """The station's own confirmatory playerState push after our "stop"
    (still "paused" device-side) must not flip the reported state back to
    paused - that would silently reopen the resume-loses-position bug this
    idle reporting exists to prevent, for as long as the push survives.
    """
    entity = FakeYandexStation()
    entity.local_state = {"aliceState": "IDLE", "playing": True}
    entity._last_local_media_id = STREAM_URL

    entity.async_set_state({"state": {**track_state(), "playing": False}})

    assert entity.state == MediaPlayerState.IDLE


def test_set_state_reports_paused_without_local_content():
    """Real Yandex Music (voice/app) playback has a genuine native pause -
    it should still show as paused, not idle.
    """
    entity = FakeYandexStation()
    entity.local_state = {"aliceState": "IDLE", "playing": True}

    entity.async_set_state({"state": {**track_state(), "playing": False}})

    assert entity.state == MediaPlayerState.PAUSED
