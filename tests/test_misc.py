from datetime import datetime

from homeassistant.components import media_source

from custom_components.yandex_station.core import utils
from custom_components.yandex_station.hass.shopping_list import RE_SHOPPING


def test_media_source():
    query1 = {"template": "{{message}}"}
    id1 = utils.encode_media_source(query1)
    assert id1 == "74656d706c6174653d7b7b6d6573736167657d7d"

    query2 = {"message": "Привет?!"}
    id2 = utils.encode_media_source({**query2})
    assert id2 == "?message=Привет?!"

    id3 = utils.encode_media_source(query1 | query2)
    assert id3 == id1 + id2

    media_id = media_source.generate_media_source_id("tts", id1)
    assert utils.decode_media_source(media_id) == query1

    media_id = media_source.generate_media_source_id("tts", id2)
    assert utils.decode_media_source(media_id) == query2

    media_id = media_source.generate_media_source_id("tts", id1 + id2)
    assert utils.decode_media_source(media_id) == query1 | query2


def test_parse_date():
    s1 = "Tue, 16 Jan 2024 04:57:06 GMT"  # RFC 822
    s2 = "2024-01-16T04:57:05Z"  # RFC 3339
    d1 = datetime.strptime(s1, "%a, %d %b %Y %H:%M:%S %Z")
    d2 = datetime.strptime(s2, "%Y-%m-%dT%H:%M:%SZ")
    dt = (d1 - d2).total_seconds()
    assert dt < 5


def test_shopping_list():
    s = "В вашем списке покупок сейчас лежит 3 товара:\n1) хлеб\n2) 3 йогурта\n3) колбаса"
    m = RE_SHOPPING.findall(s)
    assert m == ["хлеб", "3 йогурта", "колбаса"]


def test_fix_dialog_text():
    src = '<speaker effect="megaphone">Ехал Грека через реку <speaker effect="-">видит Грека в реке рак'
    dst = '<speaker effect="megaphone">ЕХАЛ ГРЕКА ЧЕРЕЗ РЕКУ <speaker effect="-">ВИДИТ ГРЕКА В РЕКЕ РАК'
    assert utils.fix_dialog_text(src) == dst
