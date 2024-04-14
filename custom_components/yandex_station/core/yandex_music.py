import base64
import hashlib
import hmac
import operator
import re
from datetime import datetime

from .yandex_session import YandexSession

XML = re.compile(r"<(host|path|ts|s)>([^<]+)")
ID = re.compile(r"\.(\d+)-")


async def get_mp3(session: YandexSession, player_state: dict):
    try:
        tid = player_state["id"]
        aid = ID.search(player_state["extra"]["coverURI"])[1]

        # thanks to https://github.com/MarshalX/yandex-music-api
        r = await session.get(
            f"https://api.music.yandex.net/tracks/{tid}:{aid}/download-info",
        )
        res = await r.json()

        res = sorted(
            [p for p in res["result"] if p["codec"] == "mp3"],
            key=operator.itemgetter("bitrateInKbps"),
            reverse=True,
        )

        r = await session.session.get(res[0]["downloadInfoUrl"])
        res = await r.text()

        doc = dict(XML.findall(res))

        sign = hashlib.md5(
            ("XGRlBW9FXlekgbPrRHuSiA" + doc["path"][1:] + doc["s"]).encode()
        ).hexdigest()

        return f"https://{doc['host']}/get-mp3/{sign}/{doc['ts']}{doc['path']}"

    except Exception:
        return None


async def get_lyrics(session: YandexSession, track_id: str) -> str | None:
    # thanks to https://github.com/MarshalX/yandex-music-api
    r = await session.post(
        "https://api.music.yandex.net/tracks", data={"track-ids": [track_id]}, timeout=5
    )
    raw = await r.json()
    if not raw["result"][0]["lyricsInfo"]["hasAvailableSyncLyrics"]:
        return None

    url = f"https://api.music.yandex.net/tracks/{track_id}/lyrics"
    headers = {"X-Yandex-Music-Client": "YandexMusicAndroid/24023621"}

    timestamp = int(datetime.now().timestamp())
    msg = f"{track_id}{timestamp}".encode()
    sign = hmac.new(b"p93jhgh689SBReK6ghtw62", msg, hashlib.sha256).digest()
    sign64 = base64.b64encode(sign).decode()
    params = {"timeStamp": timestamp, "sign": sign64}

    r = await session.get(url, headers=headers, params=params, timeout=5)
    raw = await r.json()
    url = raw["result"]["downloadUrl"]

    r = await session.get(url, timeout=5)
    raw = await r.read()
    return raw.decode("utf-8")
