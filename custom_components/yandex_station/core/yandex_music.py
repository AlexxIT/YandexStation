import base64
import hashlib
import hmac
from datetime import datetime

from .yandex_session import YandexSession

HEADERS = {"X-Yandex-Music-Client": "YandexMusicAndroid/24023621"}


async def get_file_info(
    session: YandexSession, track_id: int, quality: str, codecs: str
) -> dict[str, str]:
    # lossless + mp3 = 320 kbps
    # nq       + mp3 = 192 kbps
    # lossless + aac = 256 kbps
    # nq       + aac = 192 kbps
    timestamp = int(datetime.now().timestamp())
    params = {
        "ts": timestamp,
        "trackId": track_id,
        "quality": quality,  # lossless,nq,lq
        "codecs": codecs,  # flac,aac,he-aac,mp3
        "transports": "raw",
    }
    params["sign"] = sign(*params.values())[:-1]

    r = await session.get(
        "https://api.music.yandex.net/get-file-info",
        headers=HEADERS,
        params=params,
        timeout=5,
    )
    raw = await r.json()
    return raw["result"]["downloadInfo"]


async def get_lyrics(session: YandexSession, track_id: int | str) -> str | None:
    # thanks to https://github.com/MarshalX/yandex-music-api
    r = await session.post(
        "https://api.music.yandex.net/tracks", data={"track-ids": [track_id]}, timeout=5
    )
    raw = await r.json()
    if not raw["result"][0]["lyricsInfo"]["hasAvailableSyncLyrics"]:
        return None

    timestamp = int(datetime.now().timestamp())
    params = {"timeStamp": timestamp, "sign": sign(track_id, timestamp)}

    r = await session.get(
        f"https://api.music.yandex.net/tracks/{track_id}/lyrics",
        headers=HEADERS,
        params=params,
        timeout=5,
    )
    raw = await r.json()
    url = raw["result"]["downloadUrl"]

    r = await session.get(url, timeout=5)
    raw = await r.read()
    return raw.decode("utf-8")


def sign(*args) -> str:
    msg = "".join(str(i) for i in args).replace(",", "").encode()
    hmac_hash = hmac.new(b"p93jhgh689SBReK6ghtw62", msg, hashlib.sha256).digest()
    return base64.b64encode(hmac_hash).decode()
