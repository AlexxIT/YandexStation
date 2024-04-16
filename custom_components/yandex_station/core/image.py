import io
import os
import re

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1280
HEIGHT = 720
HEIGHT2 = 720 // 2


def font_path() -> str:
    dirname = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(dirname, "fonts", "DejaVuSans.ttf")


def draw_text(
    ctx: ImageDraw,
    text: str,
    box: tuple,
    anchor: str,
    fill: str | tuple,
    font: ImageFont,
    line_width: int = 20,
):
    """Draw multiline text inside box with smart anchor."""
    lines = re.findall(r"(.{1,%d})(?:\s|$)" % line_width, text)

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
        y = box[1] + (box[3] - len(lines) * font.size) // 2
    elif anchor[1] == "b":
        y = box[1] + (box[3] - len(lines) * font.size)
    else:
        raise NotImplementedError(anchor)

    for line in lines:
        ctx.text((x, y), line, anchor=align, fill=fill, font=font)
        y += font.size


def draw_cover(title: str, artist: str, cover: bytes) -> bytes:
    cover_canvas = Image.open(io.BytesIO(cover))
    assert cover_canvas.size == (400, 400)

    canvas = Image.new("RGB", (WIDTH, HEIGHT))
    canvas.paste(cover_canvas, (WIDTH - 450, (HEIGHT - 400) // 2))

    ctx = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(font_path(), 60, encoding="UTF-8")
    if title:
        draw_text(ctx, title, (0, 0, WIDTH - 450, HEIGHT2 - 25), "mb", "white", font)
    if artist:
        draw_text(
            ctx, artist, (0, HEIGHT2 + 25, WIDTH - 450, HEIGHT2), "mt", "grey", font
        )

    bytes = io.BytesIO()
    canvas.save(bytes, format="JPEG", quality=75)
    return bytes.getvalue()


def draw_lyrics(first: str | None, second: str | None) -> bytes:
    canvas = Image.new("RGB", (WIDTH, HEIGHT))

    ctx = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(font_path(), 100, encoding="UTF-8")
    if first:
        draw_text(ctx, first, (0, 50, WIDTH, HEIGHT2 - 50), "mm", "white", font)
    if second:
        draw_text(ctx, second, (0, HEIGHT2, WIDTH, HEIGHT2 - 50), "mm", "grey", font)

    bytes = io.BytesIO()
    canvas.save(bytes, format="JPEG", quality=75)
    return bytes.getvalue()


def draw_none() -> bytes:
    canvas = Image.new("RGB", (WIDTH, HEIGHT), "grey")

    bytes = io.BytesIO()
    canvas.save(bytes, format="JPEG", quality=75)
    return bytes.getvalue()
