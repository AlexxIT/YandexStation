import hashlib
import operator
import re

from .yandex_session import YandexSession

XML = re.compile(r"<(host|path|ts|s)>([^<]+)")
ID = re.compile(r"\.(\d+)-")


async def get_mp3(session: YandexSession, player_state: dict):
    try:
        tid = player_state['id']
        aid = ID.search(player_state["extra"]["coverURI"])[1]

        # thanks to https://github.com/MarshalX/yandex-music-api
        r = await session.get(
            f"https://api.music.yandex.net/tracks/{tid}:{aid}/download-info",
        )
        res = await r.json()

        res = sorted(
            [p for p in res["result"] if p["codec"] == "mp3"],
            key=operator.itemgetter("bitrateInKbps"), reverse=True
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
