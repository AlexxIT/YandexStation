import logging
import re

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..core.yandex_dialog import YandexDialog, normalize_item
from .shopping_list import looks_like_list, read_list

_LOGGER = logging.getLogger(__package__)

# Алиса отдаёт список строками «1) молоко»
RE_TODO = re.compile(r"^\d+\) (.+)$", re.MULTILINE)

STORE_VERSION = 1
STORE_KEY = "yandex_station.todo"

# предохранитель: если навык перестанет удалять пункты, синк не зациклится
MAX_STEPS = 50


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
    """Пункты Алисы, которые надо удалить.

    Два случая: пункт отмечен выполненным в ToDo или пользователь удалил его из
    ToDo (Алиса сама об этом не сообщает, поэтому сравниваем с прошлым набором).
    Возвращаем названия, а не номера строк — см. shopping_for_remove().
    """
    alice_items = RE_TODO.findall(alice_data)

    current = {
        normalize_item(item["summary"]) for item in todo_items if item.get("summary")
    }
    completed = {
        normalize_item(item["summary"])
        for item in todo_items
        if item.get("summary") and item.get("status") == "completed"
    }
    # был в прошлом синке, но из ToDo его убрали
    deleted = set(map(normalize_item, previous_alice_items)) - current

    result: list[str] = []
    for name in alice_items:
        normalized = normalize_item(name)
        if (normalized in completed or normalized in deleted) and name not in result:
            result.append(name)
    return result


async def todo_for_add(
    todo_items: list[dict], alice_data: str, previous_alice_items: set[str]
) -> list[str]:
    """Пункты ToDo, которых нет у Алисы: выполненные и удалённые не возвращаем."""
    alice_items = {normalize_item(i) for i in RE_TODO.findall(alice_data)}
    previous = set(map(normalize_item, previous_alice_items))

    result = []

    for item in todo_items:
        status = item.get("status", "needs_action")
        summary = item.get("summary")

        if status == "completed" or not summary:
            continue

        name = normalize_item(summary)

        # Элемент уже есть у Алисы
        if name in alice_items:
            continue

        # Раньше был у Алисы, но пользователь удалил
        if name in previous:
            continue

        result.append(summary)

    return result


async def todo_save(hass: HomeAssistant, entity_id: str, alice_data: str) -> None:
    """Приводит ToDo к состоянию Алисы: лишнее удаляет, недостающее добавляет."""
    alice_names = RE_TODO.findall(alice_data)

    if not alice_names and not looks_like_list(alice_data):
        # не список, а посторонний ответ — затирать ToDo нельзя
        _LOGGER.warning(
            "todo_save: answer is not a list, list left as is: %r", alice_data[:80]
        )
        return

    alice_items = {normalize_item(i) for i in alice_names}

    items = await get_todo_items(hass, entity_id)

    existing = {
        normalize_item(item["summary"]): item for item in items if item.get("summary")
    }

    # Удаляем отсутствующие
    for name, item in existing.items():
        if name not in alice_items:
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
                    _LOGGER.exception("Failed to remove todo item: %s", name)

    # Добавляем новые
    for name in alice_names:
        if normalize_item(name) not in existing:
            try:
                await hass.services.async_call(
                    "todo",
                    "add_item",
                    {"entity_id": entity_id, "item": name},
                    blocking=True,
                )
            except Exception:
                _LOGGER.exception("Failed to add todo item: %s", name)


async def shopping_sync(
    hass: HomeAssistant, dialog: YandexDialog, entity_id: str
) -> None:
    """Синхронизирует произвольный список ToDo с Алисой.

    Порядок тот же, что в списке покупок: удалить, добавить, затем зеркалить.
    Ошибки только логируем — синк вызывается из play_media.
    """
    try:
        # Элементы из списка Home Assistant
        items = await get_todo_items(hass, entity_id)

        text = await read_list(dialog)

        store = Store(hass, STORE_VERSION, STORE_KEY)
        store_data = await store.async_load() or {}

        # Алиса не сообщает, что пользователь удалил пункт руками, поэтому
        # помним прошлый синхронизированный набор и считаем разницу
        previous_alice_items = set(store_data.get(entity_id) or [])

        # Удаляем выполненные: по одному названию, с перечитыванием списка
        steps = 0
        while for_remove := todo_for_remove(items, text, previous_alice_items):
            if steps >= MAX_STEPS:
                _LOGGER.warning("todo_sync: too many removal steps, stopped")
                break
            steps += 1

            await dialog.send(f"Удали из списка покупок {for_remove[0]}")
            fresh = await read_list(dialog)
            if fresh == text:
                # список не изменился: команду не поняли, повторять бессмысленно
                _LOGGER.warning(
                    "todo_sync: Alice did not remove %r, stopped", for_remove[0]
                )
                break
            text = fresh

        # Добавляем новые элементы в список по одному
        if for_add := await todo_for_add(items, text, previous_alice_items):
            for item in for_add:
                await dialog.send(f"Добавь в список покупок {item}")
            text = await read_list(dialog)

        # Сохраняем изменения из Алисы в ToDo
        await todo_save(hass, entity_id, text)

        # Обновляем Store
        store_data[entity_id] = set(RE_TODO.findall(text))
        await store.async_save(store_data)

        # Раньше здесь отправлялась команда «Стоп»: колонка зачитывала список
        # вслух, и её надо было останавливать. Облачный диалог молчит, команда
        # больше не нужна

    except Exception as e:
        _LOGGER.error("todo_sync", exc_info=e)
