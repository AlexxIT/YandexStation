import logging
import re
import uuid
from collections.abc import Callable

from homeassistant.components.shopping_list import ShoppingData
from homeassistant.core import HomeAssistant

from ..core.yandex_glagol import YandexGlagol

try:
    from homeassistant.const import EVENT_SHOPPING_LIST_UPDATED
except ImportError:
    EVENT_SHOPPING_LIST_UPDATED = "shopping_list_updated"

_LOGGER = logging.getLogger(__package__)

RE_SHOPPING = re.compile(r"^\d+\) (.+)$", re.MULTILINE)

# Алиса отвечает «не найдено» и ничего не удаляет, если в одном «Удали»
# больше 4 индексов. Режем до отправки, а не после ошибки.
MAX_REMOVE_INDEXES = 4
MAX_REMOVE_ROUNDS = 30
NOT_FOUND_MARK = "не найдено"


def _is_completed(item: dict) -> bool:
    """needs_action и незавершённые позиции нельзя выбирать к удалению."""
    status = item.get("status")
    if status == "needs_action":
        return False
    if status == "completed":
        return True
    return bool(item.get("complete"))


def shopping_for_remove(shopping_data: ShoppingData, alice_data: str) -> list[str]:
    alice_items = RE_SHOPPING.findall(alice_data)
    for_remove = [
        alice_items.index(item["name"])
        for item in shopping_data.items
        if _is_completed(item) and item["name"] in alice_items
    ]
    return [str(i + 1) for i in sorted(for_remove)]


def shopping_for_add(shopping_data: ShoppingData, alice_data: str) -> list[str]:
    alice_items = RE_SHOPPING.findall(alice_data)
    return [
        item["name"]
        for item in shopping_data.items
        if not _is_completed(item)
        and item["name"] not in alice_items
        and not str(item.get("id") or "").startswith("alice")
    ]


def card_text(card: dict | None) -> str:
    if not isinstance(card, dict):
        return ""
    text = card.get("text")
    return text if isinstance(text, str) else ""


def alice_not_found(card: dict | None) -> bool:
    return NOT_FOUND_MARK in card_text(card).casefold()


def remove_command(indexes: list[str], limit: int) -> str:
    return "Удали " + ", ".join(indexes[:limit])


def removal_stalled(
    previous_text: str,
    remove_card: dict | None,
    refreshed: dict | None,
    parse_items: Callable[[str], list[str]],
) -> bool:
    """Та же команда удаления не должна повторяться, если список не изменился."""
    refreshed_text = card_text(refreshed)
    if previous_text and not refreshed_text:
        return True
    previous_items = tuple(parse_items(previous_text or ""))
    current_items = tuple(parse_items(refreshed_text))
    rejected = alice_not_found(remove_card) or alice_not_found(refreshed)
    if current_items == previous_items:
        return True
    # Ответ «не найдено» без списка — не успешная очистка.
    if rejected and previous_items and not current_items:
        return True
    return False


def shopping_save(hass: HomeAssistant, shopping_data: ShoppingData, alice_data: str):
    alice_items = RE_SHOPPING.findall(alice_data)

    old_items = {i["name"]: i for i in shopping_data.items}
    new_items = {}
    for name in alice_items:
        old = old_items.get(name)
        if old is None:
            new_items[name] = {
                "name": name,
                "id": f"alice{uuid.uuid4().hex}",
                "complete": False,
            }
            continue
        old_id = str(old.get("id") or "")
        # Алиса не удалила позицию: не сбрасываем завершённый флаг.
        # id с префиксом alice сохраняем, чтобы следующий sync не добавил её снова.
        new_items[name] = {
            "name": name,
            "id": old_id if old_id.startswith("alice") else f"alice{uuid.uuid4().hex}",
            "complete": _is_completed(old),
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

        payload = {"command": "sendText", "text": "Что в списке покупок"}
        card = await glagol.send(payload)

        rounds = 0
        while for_remove := shopping_for_remove(data, card["text"]):
            rounds += 1
            if rounds > MAX_REMOVE_ROUNDS:
                _LOGGER.error("shopping_sync: remove round limit reached")
                break
            # Чанк до отправки. Повтор той же команды при неизменном списке
            # зацикливает колонку на «не найдено».
            text = remove_command(for_remove, MAX_REMOVE_INDEXES)
            previous_text = card["text"]
            remove_card = await glagol.send({"command": "sendText", "text": text})
            refreshed = await glagol.send(payload)
            if removal_stalled(
                previous_text, remove_card, refreshed, RE_SHOPPING.findall
            ):
                if alice_not_found(remove_card) or alice_not_found(refreshed):
                    _LOGGER.warning(
                        "shopping_sync: Alice returned not found and list did not change, stop retry: %s",
                        text,
                    )
                else:
                    _LOGGER.warning(
                        "shopping_sync: list unchanged after %s, stop retry", text
                    )
                break
            card = refreshed

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
