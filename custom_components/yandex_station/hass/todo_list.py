import logging
import re

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..core.yandex_glagol import YandexGlagol

_LOGGER = logging.getLogger(__package__)

RE_TODO = re.compile(r"^\d+\) (.+)$", re.MULTILINE)

STORE_VERSION = 1
STORE_KEY = "yandex_station.todo"


async def get_todo_items(hass: HomeAssistant, entity_id: str) -> list[dict]:
    response = await hass.services.async_call(
        "todo",
        "get_items",
        {"entity_id": entity_id},
        blocking=True,
        return_response=True,
    )

    if not response:
        return []

    data = response.get(entity_id)

    if not data:
        return []

    return data.get("items", [])


def todo_for_remove(
    todo_items: list[dict], alice_data: str, previous_alice_items: set[str]
) -> list[str]:
    alice_items = RE_TODO.findall(alice_data)

    current_todo_items = {
        item.get("summary") for item in todo_items if item.get("summary")
    }

    for_remove = []
    alice_indexes = {item: i for i, item in enumerate(alice_items)}

    # Помечены как завершенные
    for item in todo_items:
        summary = item.get("summary")
        if summary and item.get("status") == "completed" and summary in alice_items:
            for_remove.append(alice_indexes[summary])

    # Удалены пользователем из ToDo
    for summary in previous_alice_items - current_todo_items:
        if summary in alice_items:
            for_remove.append(alice_indexes[summary])

    return [str(i + 1) for i in sorted(set(for_remove))]


async def todo_for_add(
    todo_items: list[dict], alice_data: str, previous_alice_items: set[str]
) -> list[str]:
    alice_items = set(RE_TODO.findall(alice_data))

    result = []

    for item in todo_items:
        status = item.get("status", "needs_action")
        summary = item.get("summary")

        if status == "completed" or not summary:
            continue

        # Элемент уже есть у Алисы
        if summary in alice_items:
            continue

        # Раньше был у Алисы, но пользователь удалил
        if summary in previous_alice_items:
            continue

        result.append(summary)

    return result


async def todo_save(hass: HomeAssistant, entity_id: str, alice_data: str) -> None:
    alice_items = set(RE_TODO.findall(alice_data))

    items = await get_todo_items(hass, entity_id)

    existing = {item.get("summary"): item for item in items if item.get("summary")}

    # Удаляем отсутствующие
    for summary, item in existing.items():
        if summary not in alice_items:
            uid = item.get("uid") or item.get("id") or item.get("item_id")

            if uid:
                try:
                    await hass.services.async_call(
                        "todo",
                        "remove_item",
                        {"entity_id": entity_id, "item": uid},
                        blocking=True,
                    )
                except Exception:
                    _LOGGER.exception("Failed to remove todo item: %s", summary)

    # Добавляем новые
    for summary in alice_items:
        if summary not in existing:
            try:
                await hass.services.async_call(
                    "todo",
                    "add_item",
                    {"entity_id": entity_id, "item": summary},
                    blocking=True,
                )
            except Exception:
                _LOGGER.exception("Failed to add todo item: %s", summary)


async def shopping_sync(
    hass: HomeAssistant, glagol: YandexGlagol, entity_id: str
) -> None:
    try:
        # Элементы из списка Home Assistant
        items = await get_todo_items(hass, entity_id)

        payload = {"command": "sendText", "text": "Что в списке покупок"}
        card = await glagol.send(payload)

        store = Store(hass, STORE_VERSION, STORE_KEY)
        store_data = await store.async_load() or {}

        # Элементы ранее синхронизированные с алисой
        previous_alice_items = set(store_data.get(entity_id) or [])

        # Удаляем выполненные
        while for_remove := todo_for_remove(items, card["text"], previous_alice_items):
            # Не удаляет больше 2-х элементов за раз
            await glagol.send(
                {"command": "sendText", "text": "Удали " + ", ".join(for_remove[:2])}
            )
            card = await glagol.send(payload)

        # Добавляем новые элементы в список по одному
        if for_add := await todo_for_add(items, card["text"], previous_alice_items):
            for item in for_add:
                await glagol.send(
                    {"command": "sendText", "text": f"Добавь в список покупок {item}"}
                )
            card = await glagol.send(payload)

        # Сохраняем изменения из Алисы в ToDo
        await todo_save(hass, entity_id, card["text"])

        # Обновляем Store
        current_alice_items = set(RE_TODO.findall(card["text"]))
        store_data[entity_id] = current_alice_items
        await store.async_save(store_data)

        # Остановим алису
        await glagol.send({"command": "sendText", "text": "Стоп"})

    except Exception as e:
        _LOGGER.error("todo_sync", exc_info=e)
