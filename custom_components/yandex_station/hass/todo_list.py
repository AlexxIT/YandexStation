import logging
import re

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..core.yandex_quasar import YandexQuasar

_LOGGER = logging.getLogger(__package__)

RE_TODO = re.compile(r"^\d+\) (.+)$", re.MULTILINE)

STORE_VERSION = 1
STORE_KEY = "yandex_station.todo"


def alice_text(items: list[str]) -> str:
    """Собрать нумерованный текст в формате карточки Алисы (под RE_TODO)."""
    return "\n".join(f"{i + 1}) {name}" for i, name in enumerate(items))


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
    hass: HomeAssistant, quasar: YandexQuasar, entity_id: str
) -> None:
    try:
        # Элементы из списка Home Assistant
        items = await get_todo_items(hass, entity_id)

        # Полностью облачный синк (стриминговая Алиса убила локальный glagol-путь,
        # issue #631): читаем и пишем список Алисы через rpc.alice notes API.
        note = await quasar.get_shopping_note()
        if note is None:
            _LOGGER.warning("todo_sync: облачный «Список покупок» не найден")
            return

        note_id = note["note_id"]
        alice = quasar.note_active_items(note)  # {текст: subtask_id}

        store = Store(hass, STORE_VERSION, STORE_KEY)
        store_data = await store.async_load() or {}

        # Элементы ранее синхронизированные с алисой
        previous_alice_items = set(store_data.get(entity_id) or [])
        current_todo = {item.get("summary") for item in items if item.get("summary")}

        # Выполненные в ToDo → удалить у Алисы (галка = куплено = убрать из
        # списка, как в исходном glagol-синке)
        for item in items:
            summary = item.get("summary")
            if summary and item.get("status") == "completed" and summary in alice:
                await quasar.delete_shopping_item(note_id, alice[summary])

        # Удалённые пользователем из ToDo → удалить у Алисы
        for summary in previous_alice_items - current_todo:
            if summary in alice:
                await quasar.delete_shopping_item(note_id, alice[summary])

        # Добавляем Алисе новые активные элементы (которых нет у неё и которые
        # пользователь ранее не удалял из Алисы)
        for item in items:
            status = item.get("status", "needs_action")
            summary = item.get("summary")
            if status == "completed" or not summary:
                continue
            if summary in alice or summary in previous_alice_items:
                continue
            await quasar.add_shopping_item(note_id, summary)

        # Перечитать актуальный список Алисы, отразить в ToDo и обновить Store
        note = await quasar.get_shopping_note()
        card_text = alice_text(list(quasar.note_active_items(note).keys()))
        await todo_save(hass, entity_id, card_text)

        store_data[entity_id] = set(RE_TODO.findall(card_text))
        await store.async_save(store_data)
    except Exception as e:
        _LOGGER.error("todo_sync", exc_info=e)
