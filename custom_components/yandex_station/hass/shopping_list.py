import logging
import re
import uuid
from collections.abc import Callable

from homeassistant.components.shopping_list import ShoppingData
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from ..core.yandex_glagol import YandexGlagol
from ..core.yandex_uniproxy import read_shopping_text

try:
    from homeassistant.const import EVENT_SHOPPING_LIST_UPDATED
except ImportError:
    EVENT_SHOPPING_LIST_UPDATED = "shopping_list_updated"

_LOGGER = logging.getLogger(__package__)

RE_SHOPPING = re.compile(r"^\d+\) (.+)$", re.MULTILINE)


def shopping_for_remove(shopping_data: ShoppingData, alice_data: str) -> list[str]:
    alice_items = RE_SHOPPING.findall(alice_data)
    for_remove = [
        alice_items.index(item["name"])
        for item in shopping_data.items
        if item["complete"] and item["name"] in alice_items
    ]
    return [str(i + 1) for i in sorted(for_remove)]


def shopping_for_add(shopping_data: ShoppingData, alice_data: str) -> list[str]:
    alice_items = RE_SHOPPING.findall(alice_data)
    return [
        item["name"]
        for item in shopping_data.items
        if not item["complete"]
        and item["name"] not in alice_items
        and not item["id"].startswith("alice")
    ]


async def shopping_text_from_assistant(glagol: YandexGlagol) -> str:
    http = getattr(getattr(glagol, "session", None), "_session", None)
    if http is None:
        raise HomeAssistantError("Missing shopping list text")
    try:
        text = await read_shopping_text(http)
    except Exception as e:
        raise HomeAssistantError("Missing shopping list text") from e
    if not isinstance(text, str) or not text.strip():
        raise HomeAssistantError("Missing shopping list text")
    return text


async def shopping_read(glagol: YandexGlagol) -> str:
    card = await glagol.send({"command": "sendText", "text": "Что в списке покупок"})
    if (
        not isinstance(card, dict)
        or "error" in card
        or card.get("status", "SUCCESS") != "SUCCESS"
    ):
        raise HomeAssistantError("Failed to read shopping list")
    text = card.get("text")
    if not isinstance(text, str) or not text.strip():
        text = await shopping_text_from_assistant(glagol)

    lines = text.strip().splitlines()
    count = re.fullmatch(
        r"В вашем списке покупок (?:сейчас )?лежит (\d+) товар[а-я]*:",
        lines[0],
        re.IGNORECASE,
    )
    if count:
        rows = lines[1:]
        if int(count[1]) != len(rows) or any(
            not re.fullmatch(rf"{i}\) \S.*", row) for i, row in enumerate(rows, 1)
        ):
            raise HomeAssistantError("Incomplete shopping list")
    elif not re.fullmatch(
        r"(?:Ваш )?список покупок (?:пока )?пуст[.!]?"
        r"|В вашем списке покупок пока ничего нет[.!]?",
        text.strip(),
        re.IGNORECASE,
    ):
        raise HomeAssistantError("Unrecognized shopping list")
    return text


async def remove_in_chunks(
    glagol: YandexGlagol,
    indexes_for: Callable[[str], list[str]],
    chunk: int = 3,
) -> tuple[str, bool]:
    """Удалять только по свежим индексам; уменьшать пачку после явного отказа."""
    text = await shopping_read(glagol)
    skipped: set[str] = set()
    while True:
        names = RE_SHOPPING.findall(text)
        indexes = [i for i in indexes_for(text) if names[int(i) - 1] not in skipped][
            :chunk
        ]
        if not indexes:
            return text, not skipped
        card = await glagol.send(
            {"command": "sendText", "text": "Удали " + ", ".join(indexes)}
        )
        if (
            not isinstance(card, dict)
            or not card
            or "error" in card
            or card.get("status", "SUCCESS") != "SUCCESS"
        ):
            raise HomeAssistantError("Shopping list deletion was not confirmed")
        refreshed = await shopping_read(glagol)
        current = RE_SHOPPING.findall(refreshed)
        if len(current) >= len(names):
            reply = card.get("text")
            if (
                current != names
                or not isinstance(reply, str)
                or "не найдено" not in reply.casefold()
            ):
                raise HomeAssistantError("Shopping list deletion made no progress")
            if len(indexes) > 1:
                chunk = len(indexes) - 1
            else:
                skipped.add(names[int(indexes[0]) - 1])
        text = refreshed


def shopping_save(hass: HomeAssistant, shopping_data: ShoppingData, alice_data: str):
    alice_items = RE_SHOPPING.findall(alice_data)

    old_items = {i["name"]: i for i in shopping_data.items}
    new_items = {
        name: {
            "name": name,
            "id": f"alice{uuid.uuid4().hex}",
            "complete": old_items.get(name, {}).get("complete", False),
        }
        for name in alice_items
    }

    shopping_data.items = list(new_items.values())
    hass.async_add_executor_job(shopping_data.save)

    # noinspection PyProtectedMember
    shopping_data._async_notify()

    for name, item in old_items.items():
        if name not in new_items:
            hass.bus.async_fire(
                EVENT_SHOPPING_LIST_UPDATED, {"action": "remove", "item": item}
            )

    for name, item in new_items.items():
        if name not in old_items:
            hass.bus.async_fire(
                EVENT_SHOPPING_LIST_UPDATED, {"action": "add", "item": item}
            )


async def shopping_sync(hass: HomeAssistant, glagol: YandexGlagol):
    entries = hass.config_entries.async_entries("shopping_list")
    if not entries:
        return

    try:
        # magic for support new version after HA 2026.5 and old version
        data = getattr(entries[0], "runtime_data", hass.data.get("shopping_list"))

        text, complete = await remove_in_chunks(
            glagol, lambda text: shopping_for_remove(data, text)
        )

        if for_add := shopping_for_add(data, text):
            for item in for_add:
                # плохо работает, если добавлять всё сразу через запятую
                text = f"Добавь в список покупок {item}"
                await glagol.send({"command": "sendText", "text": text})
            # обновим после изменений
            text = await shopping_read(glagol)

        shopping_save(hass, data, text)
        if not complete:
            raise HomeAssistantError("Some shopping list items could not be removed")
    except Exception as e:
        _LOGGER.error("shopping_sync", exc_info=e)
        raise
