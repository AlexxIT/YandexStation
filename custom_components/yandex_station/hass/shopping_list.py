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

# Наблюдаемый сбой — пачка больше 4–5. Первая команда уже меньше этой зоны,
# до ответа Алисы. Если чанк отклонён, ту же команду не повторяем,
# но пробуем меньший чанк, вплоть до одной позиции.
INITIAL_REMOVE_CHUNK = 3
MAX_REMOVE_ROUNDS = 80
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


def _selectable_indexes(
    indexes: list[str], names: list[str], skipped: set[str]
) -> list[str]:
    selected = []
    for index in indexes:
        position = int(index) - 1
        if position < 0 or position >= len(names):
            continue
        if names[position] in skipped:
            continue
        selected.append(index)
    return selected


async def remove_in_chunks(
    glagol: YandexGlagol,
    card: dict,
    list_payload: dict,
    indexes_for: Callable[[str], list[str]],
    parse_items: Callable[[str], list[str]],
    initial_chunk: int,
    log_prefix: str,
) -> dict:
    """Удалить completed-позиции, уменьшая чанк после отказа.

    Одиночно отклонённая позиция пропускается: колонка не зацикливается,
    остальные completed ещё пробуются.
    """
    chunk = max(1, initial_chunk)
    attempted: set[tuple[str, tuple[str, ...]]] = set()
    skipped: set[str] = set()
    rounds = 0

    while True:
        rounds += 1
        if rounds > MAX_REMOVE_ROUNDS:
            _LOGGER.error("%s: remove round limit reached", log_prefix)
            break

        current_text = card_text(card)
        names = parse_items(current_text)
        selectable = _selectable_indexes(indexes_for(current_text), names, skipped)
        if not selectable:
            break

        limit = min(chunk, len(selectable))
        command = remove_command(selectable, limit)
        signature = (command, tuple(names))
        if signature in attempted:
            if limit <= 1:
                skipped.add(names[int(selectable[0]) - 1])
            else:
                chunk = limit - 1
            continue

        attempted.add(signature)
        remove_card = await glagol.send({"command": "sendText", "text": command})
        refreshed = await glagol.send(list_payload)
        if removal_stalled(current_text, remove_card, refreshed, parse_items):
            if limit <= 1:
                skipped.add(names[int(selectable[0]) - 1])
                _LOGGER.warning(
                    "%s: single item not removed, continue with the rest: %s",
                    log_prefix,
                    command,
                )
            else:
                chunk = limit - 1
                _LOGGER.warning(
                    "%s: chunk rejected, try %s: %s", log_prefix, chunk, command
                )
            continue

        card = refreshed

    return card


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
        card = await remove_in_chunks(
            glagol,
            card,
            payload,
            lambda text: shopping_for_remove(data, text),
            RE_SHOPPING.findall,
            INITIAL_REMOVE_CHUNK,
            "shopping_sync",
        )

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
