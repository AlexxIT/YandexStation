import logging
import re
import uuid

from homeassistant.components.shopping_list import ShoppingData
from homeassistant.core import HomeAssistant

from ..core.yandex_dialog import YandexDialog, normalize_item

try:
    from homeassistant.const import EVENT_SHOPPING_LIST_UPDATED
except ImportError:
    EVENT_SHOPPING_LIST_UPDATED = "shopping_list_updated"

_LOGGER = logging.getLogger(__package__)

# Алиса отдаёт список строками «1) молоко» — номер нужен только для чтения
RE_SHOPPING = re.compile(r"^\d+\) (.+)$", re.MULTILINE)

QUERY = "Что в списке покупок"
# предохранитель: если навык перестанет удалять пункты, синк не зациклится
MAX_STEPS = 50


def shopping_for_remove(shopping_data: ShoppingData, alice_data: str) -> list[str]:
    """Пункты Алисы, отмеченные как купленные в HA.

    Возвращаем именно названия, а не номера строк: на «Удали <номер>» навык
    отвечает без текстовой карточки, подтвердить удаление нельзя, и синк падал
    с «no text answer». По названию ответ приходит нормальный.
    """
    alice_items = RE_SHOPPING.findall(alice_data)
    completed = {
        normalize_item(item["name"]) for item in shopping_data.items if item["complete"]
    }

    result: list[str] = []
    for name in alice_items:
        if normalize_item(name) in completed and name not in result:
            result.append(name)
    return result


def shopping_for_add(shopping_data: ShoppingData, alice_data: str) -> list[str]:
    """Пункты HA, которых нет у Алисы.

    Пункты с id на «alice» — зеркало списка Алисы, обратно их не отправляем.
    """
    alice_items = {normalize_item(i) for i in RE_SHOPPING.findall(alice_data)}
    return [
        item["name"]
        for item in shopping_data.items
        if not item["complete"]
        and normalize_item(item["name"]) not in alice_items
        and not item["id"].startswith("alice")
    ]


def shopping_save(hass: HomeAssistant, shopping_data: ShoppingData, alice_data: str):
    """Переписывает список HA по ответу Алисы: HA-список — зеркало.

    id генерируем с префиксом «alice», чтобы следующий проход понимал, откуда
    взялся пункт. События шлём руками: items меняются в обход публичного API.
    """
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


async def shopping_sync(hass: HomeAssistant, dialog: YandexDialog):
    """Синхронизирует список покупок HA и Алисы.

    Порядок важен: сначала удаляем купленное, потом добавляем новое, и только
    затем зеркалим результат в HA. Ошибки только логируем — синк вызывается из
    play_media и не должен ломать саму команду.
    """
    entries = hass.config_entries.async_entries("shopping_list")
    if not entries:
        return

    try:
        # magic for support new version after HA 2026.5 and old version
        data = getattr(entries[0], "runtime_data", hass.data.get("shopping_list"))

        text = await dialog.send(QUERY)

        steps = 0
        while for_remove := shopping_for_remove(data, text):
            # Алиса удаляет один пункт за запрос; список через запятую она
            # применяет частично и не по порядку, поэтому по одному и с
            # перечитыванием: после удаления номера строк сдвигаются
            if steps >= MAX_STEPS:
                _LOGGER.warning("shopping_sync: too many removal steps, stopped")
                break
            steps += 1

            await dialog.send(f"Удали из списка покупок {for_remove[0]}")
            # обновим после изменений
            fresh = await dialog.send(QUERY)
            if fresh == text:
                # список не изменился: команду не поняли, повторять бессмысленно
                _LOGGER.warning(
                    "shopping_sync: Alice did not remove %r, stopped", for_remove[0]
                )
                break
            text = fresh

        if for_add := shopping_for_add(data, text):
            for item in for_add:
                # по одному: через запятую навык теряет часть пунктов
                await dialog.send(f"Добавь в список покупок {item}")
            # обновим после изменений
            text = await dialog.send(QUERY)

        shopping_save(hass, data, text)
    except Exception as e:
        _LOGGER.error("shopping_sync", exc_info=e)
