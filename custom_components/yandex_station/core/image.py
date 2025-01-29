import io
import os
import re

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1280
HEIGHT = 720
WIDTH2 = WIDTH // 2
HEIGHT2 = HEIGHT // 2
HEIGHT6 = HEIGHT // 6


def font_path() -> str:
    dirname = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(dirname, "fonts", "DejaVuSans.ttf")


def draw_text(
    ctx: ImageDraw,
    text: str,
    box: tuple,
    anchor: str,
    fill: str | tuple,
    font_size: int,
    line_width: int = 20,
):
    """Draw multiline text inside box with smart anchor."""
    lines = re.findall(r"(.{1,%d})(?:\s|$)" % line_width, text)
    if (font_size > 70 and len(lines) > 3) or (font_size <= 70 and len(lines) > 4):
        return draw_text(ctx, text, box, anchor, fill, font_size - 10, line_width + 3)

    # https://pillow.readthedocs.io/en/stable/handbook/text-anchors.html#text-anchors
    if anchor[0] == "l":
        x = box[0]
        align = "la"  # left-ascender
    elif anchor[0] == "m":
        x = box[0] + (box[2]) // 2
        align = "ma"  # middle-ascender
    elif anchor[0] == "r":
        x = box[0] + box[2]
        align = "ra"  # right-ascender
    else:
        raise NotImplementedError(anchor)

    if anchor[1] == "t":
        y = box[1]
    elif anchor[1] == "m":
        y = box[1] + (box[3] - len(lines) * font_size) // 2
    elif anchor[1] == "b":
        y = box[1] + (box[3] - len(lines) * font_size)
    else:
        raise NotImplementedError(anchor)

    font = ImageFont.truetype(font_path(), font_size, encoding="UTF-8")

    for line in lines:
        ctx.text((x, y), line, anchor=align, fill=fill, font=font)
        y += font_size


def draw_cover(title: str, artist: str, cover: bytes) -> bytes:
    cover_canvas = Image.open(io.BytesIO(cover))
    assert cover_canvas.size == (400, 400)

    canvas = Image.new("RGB", (WIDTH, HEIGHT))
    canvas.paste(cover_canvas, (WIDTH2 - 200, HEIGHT6 * 2 - 200))

    ctx = ImageDraw.Draw(canvas)
    if title:
        draw_text(ctx, title, (0, HEIGHT6 * 4, WIDTH, HEIGHT6), "mb", "white", 60, 35)
    if artist:
        draw_text(ctx, artist, (0, HEIGHT6 * 5, WIDTH, HEIGHT6), "mt", "grey", 50, 40)

    bytes = io.BytesIO()
    canvas.save(bytes, format="JPEG", quality=75)
    return bytes.getvalue()


def draw_lyrics(first: str | None, second: str | None) -> bytes:
    canvas = Image.new("RGB", (WIDTH, HEIGHT))

    ctx = ImageDraw.Draw(canvas)
    if first:
        draw_text(ctx, first, (0, 50, WIDTH, HEIGHT2 - 50), "mm", "white", 100)
    if second:
        draw_text(ctx, second, (0, HEIGHT2, WIDTH, HEIGHT2 - 50), "mm", "grey", 100)

    bytes = io.BytesIO()
    canvas.save(bytes, format="JPEG", quality=75)
    return bytes.getvalue()


def draw_none() -> bytes:
    canvas = Image.new("RGB", (WIDTH, HEIGHT), "grey")

    bytes = io.BytesIO()
    canvas.save(bytes, format="JPEG", quality=75)
    return bytes.getvalue()
