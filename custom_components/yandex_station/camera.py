import asyncio
import logging
import re
from datetime import datetime, timezone

from aiohttp import web
from homeassistant.components.camera import Camera
from homeassistant.components.media_player import MediaPlayerState, MediaType
from homeassistant.const import CONTENT_TYPE_MULTIPART
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo

from .core.const import DOMAIN
from .core.image import draw_cover, draw_lyrics, draw_none
from .core.yandex_music import get_lyrics
from .core.yandex_quasar import YandexQuasar
from .core.yandex_station import YandexStation

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]

    async_add_entities(
        [YandexLyrics(quasar, speaker) for speaker in quasar.speakers], False
    )


class YandexLyrics(Camera):
    _attr_entity_registry_enabled_default = False

    stream_clients: int = 0

    def __init__(self, quasar: YandexQuasar, device: dict):
        super().__init__()
        self.quasar = quasar
        self.device = device

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["quasar_info"]["device_id"])},
            name=self.device["name"],
        )
        self._attr_name = device["name"] + " Текст"
        self._attr_unique_id = device["quasar_info"]["device_id"] + f"_lyrics"

        self.entity_id = f"select.yandex_station_{self._attr_unique_id.lower()}"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        return await self.get_cover()

    async def handle_async_mjpeg_stream(
        self, request: web.Request
    ) -> web.StreamResponse | None:
        response = web.StreamResponse()
        response.content_type = CONTENT_TYPE_MULTIPART.format("--frameboundary")
        await response.prepare(request)

        try:
            if self.stream_clients == 0:
                self._attr_is_streaming = True
                self._async_write_ha_state()
            self.stream_clients += 1

            while True:
                if lyrics := await self.get_lyrics():
                    await self.handle_lyrics(response, lyrics, self.lyrics_content_id)
                    continue

                if cover := await self.get_cover():
                    await self.handle_cover(response, cover, self.cover_content_id)
                    continue

                await self.handle_cover(response, draw_none(), self.cover_content_id)

        finally:
            self.stream_clients -= 1
            if self.stream_clients == 0:
                self._attr_is_streaming = False
                self._async_write_ha_state()

        return response

    async def handle_lyrics(
        self, response: web.StreamResponse, lyrics: str, content_id: str
    ):
        entity: YandexStation = self.device.get("entity")
        if entity.media_position is None:
            return

        times: list[float] = []
        lines: list[str] = []
        for line in RE_LYRICS.findall(lyrics):
            ts = int(line[0]) * 60 + int(line[1]) + int(line[2]) / 100
            times.append(ts)
            lines.append(line[3])

        lyric_pos = lyric_pos_next = 0

        while entity.media_content_id == content_id:
            media_position = entity.media_position
            if entity.state == MediaPlayerState.PLAYING:
                dt = datetime.now(timezone.utc) - entity.media_position_updated_at
                media_position += dt.total_seconds()
                delay = min(lyric_pos_next - media_position, 1)
            else:
                delay = 1

            if not (lyric_pos <= media_position < lyric_pos_next):
                if media_position < times[0]:
                    lyric_pos = 0
                    lyric_pos_next = times[0]
                    image = draw_lyrics(None, lines[0])  # before first
                elif media_position > times[-1]:
                    lyric_pos = times[-1]
                    lyric_pos_next = entity.media_duration or 65535
                    image = draw_lyrics(lines[-1], None)  # last
                else:
                    for i, ts in enumerate(times):
                        if ts >= media_position:
                            lyric_pos = times[i - 1]
                            lyric_pos_next = ts
                            image = draw_lyrics(lines[i - 1], lines[i])
                            break
                    else:
                        image = draw_none()

                await write_to_mjpeg_stream(response, image)

            await asyncio.sleep(delay)

    async def handle_cover(
        self, response: web.StreamResponse, image: bytes, content_id: str
    ):
        await write_to_mjpeg_stream(response, image)

        entity: YandexStation = self.device.get("entity")
        while entity.media_content_id == content_id:
            await asyncio.sleep(1)

    cover: bytes | None = None
    cover_content_id: str = None

    async def get_cover(self) -> bytes | None:
        entity: YandexStation = self.device.get("entity")
        if not entity:
            return None

        if self.cover_content_id != entity.media_content_id:
            if entity.media_image_url:
                session = async_get_clientsession(self.hass)
                r = await session.get(entity.media_image_url, timeout=15)
                image = await r.read()

                self.cover = draw_cover(entity.media_title, entity.media_artist, image)
            else:
                self.cover = None

            self.cover_content_id = entity.media_content_id

        return self.cover

    lyrics: str | None = None
    lyrics_content_id: str = None

    async def get_lyrics(self) -> str | None:
        entity: YandexStation = self.device.get("entity")
        if not entity:
            return None

        if self.lyrics_content_id != entity.media_content_id:
            if entity.media_content_type == MediaType.MUSIC:
                self.lyrics = await get_lyrics(
                    self.quasar.session, entity.media_content_id
                )
            else:
                self.lyrics = None

            self.lyrics_content_id = entity.media_content_id

        return self.lyrics


RE_LYRICS = re.compile(
    r"^\[([0-9]{2}):([0-9]{2})\.([0-9]{2})] (.+)$", flags=re.MULTILINE
)


async def write_to_mjpeg_stream(response: web.StreamResponse, image: bytes) -> None:
    data = (
        b"--frameboundary\r\nContent-Type: image/jpeg\r\nContent-Length: "
        + str(len(image)).encode()
        + b"\r\n\r\n"
        + image
        + b"\r\n"
    )
    # two times - fix Chrome bug
    await response.write(data)
    await response.write(data)
