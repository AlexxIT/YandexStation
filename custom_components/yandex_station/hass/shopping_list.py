import logging
import re
import uuid

from homeassistant.components.shopping_list import ShoppingData
from homeassistant.core import HomeAssistant

from ..core.yandex_quasar import YandexQuasar

try:
    from homeassistant.const import EVENT_SHOPPING_LIST_UPDATED
except ImportError:
    EVENT_SHOPPING_LIST_UPDATED = "shopping_list_updated"

_LOGGER = logging.getLogger(__package__)

RE_SHOPPING = re.compile(r"^\d+\) (.+)$", re.MULTILINE)


def alice_text(items: list[str]) -> str:
    """Собрать нумерованный текст в формате карточки Алисы (под RE_SHOPPING)."""
    return "\n".join(f"{i + 1}) {name}" for i, name in enumerate(items))


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


async def shopping_sync(hass: HomeAssistant, quasar: YandexQuasar):
    entries = hass.config_entries.async_entries("shopping_list")
    if not entries:
        return

    try:
        # magic for support new version after HA 2026.5 and old version
        data = getattr(entries[0], "runtime_data", hass.data.get("shopping_list"))

        # Полностью облачный синк (стриминговая Алиса убила локальный glagol-путь,
        # issue #631): читаем и пишем список через rpc.alice notes API.
        note = await quasar.get_shopping_note()
        if note is None:
            _LOGGER.warning("shopping_sync: облачный «Список покупок» не найден")
            return

        note_id = note["note_id"]
        alice = quasar.note_active_items(note)  # {текст: subtask_id}

        # Выполненные в HA → удалить у Алисы (галка = куплено = убрать из
        # списка, как в исходном glagol-синке)
        for item in data.items:
            if item["complete"] and item["name"] in alice:
                await quasar.delete_shopping_item(note_id, alice[item["name"]])

        # Новые в HA (не из Алисы) — добавить Алисе
        for item in data.items:
            if (
                not item["complete"]
                and item["name"] not in alice
                and not item["id"].startswith("alice")
            ):
                await quasar.add_shopping_item(note_id, item["name"])

        # Перечитать актуальный список Алисы и отразить его в HA
        note = await quasar.get_shopping_note()
        card_text = alice_text(list(quasar.note_active_items(note).keys()))
        shopping_save(hass, data, card_text)
    except Exception as e:
        _LOGGER.error("shopping_sync", exc_info=e)
