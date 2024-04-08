import logging
import re
import uuid

from homeassistant.components.shopping_list import ShoppingData
from homeassistant.core import HomeAssistant

from ..core.yandex_glagol import YandexGlagol

_LOGGER = logging.getLogger(__package__)

RE_SHOPPING = re.compile(r"^\d+\) (.+)$", re.MULTILINE)


def shopping_for_remove(hass: HomeAssistant, alice_data: str) -> list[str]:
    alice_items = RE_SHOPPING.findall(alice_data)
    shopping_data: ShoppingData = hass.data["shopping_list"]
    for_remove = [
        alice_items.index(item["name"])
        for item in shopping_data.items
        if item["complete"] and item["name"] in alice_items
    ]
    return [str(i + 1) for i in sorted(for_remove)]


def shopping_for_add(hass: HomeAssistant, alice_data: str) -> list[str]:
    shopping_data: ShoppingData = hass.data["shopping_list"]
    alice_items = RE_SHOPPING.findall(alice_data)
    return [
        item["name"]
        for item in shopping_data.items
        if not item["complete"]
        and item["name"] not in alice_items
        and not item["id"].startswith("alice")
    ]


def shopping_save(hass: HomeAssistant, alice_data: str):
    alice_items = RE_SHOPPING.findall(alice_data)
    shopping_data: ShoppingData = hass.data["shopping_list"]
    shopping_data.items = [
        {"name": name, "id": f"alice{uuid.uuid4().hex}", "complete": False}
        for name in alice_items
    ]
    hass.async_add_executor_job(shopping_data.save)


async def shopping_sync(hass: HomeAssistant, glagol: YandexGlagol):
    if "shopping_list" not in hass.data:
        return

    try:
        payload = {"command": "sendText", "text": "Что в списке покупок"}
        card = await glagol.send(payload)

        while for_remove := shopping_for_remove(hass, card["text"]):
            # не удаляет больше 5 элементов за раз
            text = "Удали " + ", ".join(for_remove[:5])
            await glagol.send({"command": "sendText", "text": text})
            # обновим после изменений
            card = await glagol.send(payload)

        if for_add := shopping_for_add(hass, card["text"]):
            for item in for_add:
                # плохо работает, если добавлять всё сразу через запятую
                text = f"Добавь в список покупок {item}"
                await glagol.send({"command": "sendText", "text": text})
            # обновим после изменений
            card = await glagol.send(payload)

        shopping_save(hass, card["text"])
    except Exception as e:
        _LOGGER.error("shopping_sync", exc_info=e)
