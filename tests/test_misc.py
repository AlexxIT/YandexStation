from homeassistant.components import media_source

from custom_components.yandex_station.core import utils


def test_media_source():
    query1 = {"template": "{{message}}"}
    id1 = utils.encode_media_source(query1)
    assert id1 == "74656d706c6174653d7b7b6d6573736167657d7d"

    query2 = {"message": "Привет?!"}
    id2 = utils.encode_media_source({**query2})
    assert id2 == "?message=Привет?!"

    id3 = utils.encode_media_source({**query1, **query2})
    assert id3 == id1 + id2

    media_id = media_source.generate_media_source_id("tts", id1)
    assert utils.decode_media_source(media_id) == query1

    media_id = media_source.generate_media_source_id("tts", id2)
    assert utils.decode_media_source(media_id) == query2

    media_id = media_source.generate_media_source_id("tts", id1 + id2)
    assert utils.decode_media_source(media_id) == {**query1, **query2}
