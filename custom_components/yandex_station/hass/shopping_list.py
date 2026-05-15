import logging
import re
import uuid

from homeassistant.components.shopping_list import ShoppingData
from homeassistant.core import HomeAssistant

from ..core.yandex_glagol import YandexGlagol

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


def shopping_save(hass: HomeAssistant, shopping_data: ShoppingData, alice_data: str):
    alice_items = RE_SHOPPING.findall(alice_data)

    new_items = {
        name: {"name": name, "id": f"alice{uuid.uuid4().hex}", "complete": False}
        for name in alice_items
    }
    old_items = {i["name"]: i for i in shopping_data.items}

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

        payload = {"command": "sendText", "text": "Что в списке покупок"}
        card = await glagol.send(payload)

        while for_remove := shopping_for_remove(data, card["text"]):
            # не удаляет больше 5 элементов за раз
            text = "Удали " + ", ".join(for_remove[:5])
            await glagol.send({"command": "sendText", "text": text})
            # обновим после изменений
            card = await glagol.send(payload)

        if for_add := shopping_for_add(data, card["text"]):
            for item in for_add:
                # плохо работает, если добавлять всё сразу через запятую
                text = f"Добавь в список покупок {item}"
                await glagol.send({"command": "sendText", "text": text})
            # обновим после изменений
            card = await glagol.send(payload)

        shopping_save(hass, data, card["text"])
    except Exception as e:
        _LOGGER.error("shopping_sync", exc_info=e)
