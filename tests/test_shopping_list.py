"""Тесты синхронизации списка покупок с Алисой.

Проверяем то, что легко сломать при следующей правке: сравнение названий,
порядок команд (сначала удаление, потом добавление), защиту от петли и то, что
список Home Assistant остаётся зеркалом списка Алисы.
"""

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.yandex_station.core.yandex_dialog import (
    YandexDialog,
    YandexDialogError,
    normalize_item,
)
from custom_components.yandex_station.hass import shopping_list as sl
from custom_components.yandex_station.hass import todo_list as tl

QUERIES = sl.QUERIES

# ---------------------------------------------------------------- helpers ----


def render(items: list[str]) -> str:
    """Ответ Алисы на «Что в списке покупок»."""
    lines = [f"В вашем списке покупок {len(items)} товара:"]
    lines += [f"{i}) {name}" for i, name in enumerate(items, 1)]
    return "\n".join(lines)


class FakeDialog(YandexDialog):
    """Диалог с Алисой, который ведёт себя как настоящий навык."""

    def __init__(self, items: list[str], ignore_delete: bool = False):
        self.items = list(items)
        self.ignore_delete = ignore_delete
        self.commands: list[str] = []
        self.noise = 0

    async def send(self, text: str, timeout: float = 25.0) -> str:
        self.commands.append(text)

        if text in QUERIES:
            return render(self.items)

        prefix = "Удали из списка покупок "
        if text.startswith(prefix):
            name = text[len(prefix) :]
            if self.ignore_delete:
                # список «не меняется» — Алиса не поняла команду
                return render(self.items)
            self.items.remove(name)
            return f"Удалила {name} из списка покупок"

        prefix = "Добавь в список покупок "
        if text.startswith(prefix):
            self.items.append(text[len(prefix) :])
            return "Добавила"

        raise AssertionError(f"неожиданная команда: {text!r}")

    def deletes(self) -> list[str]:
        prefix = "Удали из списка покупок "
        return [c[len(prefix) :] for c in self.commands if c.startswith(prefix)]

    def adds(self) -> list[str]:
        prefix = "Добавь в список покупок "
        return [c[len(prefix) :] for c in self.commands if c.startswith(prefix)]


class FakeShoppingData:
    """Минимальная замена homeassistant.components.shopping_list.ShoppingData."""

    def __init__(self, items: list[tuple[str, bool, str]] | None = None):
        self.items = [{"name": n, "complete": c, "id": i} for n, c, i in items or []]
        self.saved = False

    def save(self) -> None:
        self.saved = True

    def _async_notify(self) -> None:
        pass


class FakeHass:
    """Ровно те части hass, которые нужны синку."""

    def __init__(self, data=None, services=None):
        self.config_entries = SimpleNamespace(
            async_entries=lambda domain: [SimpleNamespace(runtime_data=data)]
        )
        # код читает hass.data как запасной вариант для старых версий HA
        self.data: dict = {}
        self.bus = SimpleNamespace(async_fire=self._fire)
        self.events: list[tuple[str, dict]] = []
        self.services = SimpleNamespace(async_call=self._call)
        self.service_calls: list[tuple[str, str, dict]] = []
        self._service_data = services or {}

    def _fire(self, event: str, data: dict) -> None:
        self.events.append((event, data))

    async def _call(self, domain, service, data, blocking=False, return_response=False):
        self.service_calls.append((domain, service, dict(data)))
        return self._service_data.get(data.get("entity_id"))

    def async_add_executor_job(self, func, *args):
        return func(*args)


# -------------------------------------------------------- normalize_item ------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Хлеб  ", "хлеб"),
        ("3 йогурта", "3 йогурта"),
        ("творог ёжик", "творог ежик"),
        ("тест   альфа", "тест альфа"),
        ("Тест Гермес Один", "тест гермес 1"),
        ("две бутылки воды", "2 бутылки воды"),
        ("двадцать яиц", "20 яиц"),
    ],
)
def test_normalize_item(raw: str, expected: str):
    assert normalize_item(raw) == expected


def test_normalize_item_keeps_unknown_words():
    # название, которого нет в таблице числительных, не должно пострадать
    assert normalize_item("молоко 3,2%") == "молоко 3,2%"


# ------------------------------------------------- shopping_for_remove/add ---


def test_for_remove_returns_names_not_indexes():
    data = FakeShoppingData([("молоко", True, "a1"), ("хлеб", False, "a2")])
    text = render(["хлеб", "молоко"])

    # именно название: на «Удали 2» навык больше не отвечает карточкой
    assert sl.shopping_for_remove(data, text) == ["молоко"]


def test_for_remove_uses_normalize():
    data = FakeShoppingData([("тест 2", True, "a1")])
    text = render(["тест два"])

    assert sl.shopping_for_remove(data, text) == ["тест два"]


def test_for_remove_skips_items_absent_in_alice():
    data = FakeShoppingData([("молоко", True, "a1")])

    assert sl.shopping_for_remove(data, render(["хлеб"])) == []


def test_for_remove_deduplicates():
    data = FakeShoppingData([("молоко", True, "a1")])
    text = render(["молоко", "молоко"])

    assert sl.shopping_for_remove(data, text) == ["молоко"]


def test_for_add_skips_alice_mirror_and_completed():
    data = FakeShoppingData(
        [
            ("молоко", False, "alice1"),  # пришло из Алисы
            ("хлеб", False, "ha2"),  # новое из HA
            ("соль", True, "ha3"),  # уже куплено
            ("сыр", False, "ha4"),  # уже есть у Алисы
        ]
    )
    text = render(["сыр"])

    assert sl.shopping_for_add(data, text) == ["хлеб"]


def test_for_add_ignores_case_and_numerals():
    data = FakeShoppingData([("Тест Два", False, "ha1")])

    assert sl.shopping_for_add(data, render(["тест 2"])) == []


# ------------------------------------------------------------ shopping_save --


def test_save_mirrors_list_and_fires_events():
    data = FakeShoppingData([("молоко", False, "alice1"), ("хлеб", False, "ha2")])
    hass = FakeHass(data)

    sl.shopping_save(hass, data, render(["молоко", "сыр"]))

    assert [i["name"] for i in data.items] == ["молоко", "сыр"]
    assert all(i["id"].startswith("alice") for i in data.items)
    assert data.saved is True

    actions = {(e[1]["action"], e[1]["item"]["name"]) for e in hass.events}
    assert actions == {("remove", "хлеб"), ("add", "сыр")}
    assert all(e[0] == sl.EVENT_SHOPPING_LIST_UPDATED for e in hass.events)


def test_save_is_idempotent():
    data = FakeShoppingData([("молоко", False, "alice1")])
    hass = FakeHass(data)

    sl.shopping_save(hass, data, render(["молоко"]))
    hass.events.clear()
    sl.shopping_save(hass, data, render(["молоко"]))

    assert hass.events == []


# ------------------------------------------------------------ shopping_sync --


def run(coro):
    return asyncio.run(coro)


def test_sync_removes_then_adds_then_mirrors():
    data = FakeShoppingData([("молоко", True, "alice1"), ("хлеб", False, "ha2")])
    hass = FakeHass(data)
    dialog = FakeDialog(["молоко", "яйца"])

    run(sl.shopping_sync(hass, dialog))

    # купленное (молоко) удалено, новое (хлеб) добавлено
    assert dialog.items == ["яйца", "хлеб"]
    assert dialog.deletes() == ["молоко"]
    assert dialog.adds() == ["хлеб"]
    # и HA теперь зеркало Алисы
    assert [i["name"] for i in data.items] == ["яйца", "хлеб"]


def test_sync_deletes_one_by_one():
    data = FakeShoppingData(
        [("молоко", True, "alice1"), ("сыр", True, "alice2"), ("хлеб", False, "ha3")]
    )
    hass = FakeHass(data)
    dialog = FakeDialog(["молоко", "сыр", "хлеб"])

    run(sl.shopping_sync(hass, dialog))

    # по одной команде на пункт, никаких «Удали 1, 2»
    assert dialog.deletes() == ["молоко", "сыр"]
    assert dialog.items == ["хлеб"]


def test_sync_stops_when_alice_ignores_delete():
    data = FakeShoppingData([("молоко", True, "alice1")])
    hass = FakeHass(data)
    dialog = FakeDialog(["молоко"], ignore_delete=True)

    run(sl.shopping_sync(hass, dialog))

    # попытка одна: список не изменился, повторять бессмысленно
    assert dialog.deletes() == ["молоко"]
    assert [i["name"] for i in data.items] == ["молоко"]


def test_sync_respects_max_steps(monkeypatch):
    monkeypatch.setattr(sl, "MAX_STEPS", 2)

    data = FakeShoppingData([("молоко", True, "alice1")])
    hass = FakeHass(data)

    class EndlessDialog(FakeDialog):
        async def send(self, text: str, timeout: float = 25.0) -> str:
            if text in QUERIES:
                self.noise += 1
                self.commands.append(text)
                # список «меняется», но купленный пункт остаётся на месте
                return render(self.items + ["шум"] * self.noise)
            return await super().send(text, timeout)

    dialog = EndlessDialog(["молоко"], ignore_delete=True)

    run(sl.shopping_sync(hass, dialog))

    assert len(dialog.deletes()) == 2  # MAX_STEPS


def test_sync_logs_and_survives_dialog_error(caplog):
    data = FakeShoppingData([("молоко", True, "alice1")])
    hass = FakeHass(data)

    class BrokenDialog:
        async def send(self, text: str, timeout: float = 25.0) -> str:
            raise YandexDialogError("no text answer from Alice")

    with caplog.at_level("ERROR"):
        run(sl.shopping_sync(hass, BrokenDialog()))

    # важно: исключение не улетает в play_media, список не перезаписывается
    assert "shopping_sync" in caplog.text
    assert [i["name"] for i in data.items] == ["молоко"]


def test_sync_without_shopping_list_component():
    hass = FakeHass(data=None)
    hass.config_entries = SimpleNamespace(async_entries=lambda domain: [])

    run(sl.shopping_sync(hass, FakeDialog([])))


# ---------------------------------------------------------------- todo path --


def test_todo_for_remove_completed_and_deleted():
    items = [
        {"summary": "молоко", "status": "completed"},
        {"summary": "хлеб", "status": "needs_action"},
    ]
    text = render(["молоко", "хлеб", "яйца"])

    assert tl.todo_for_remove(items, text, {"яйца"}) == ["молоко", "яйца"]


def test_todo_for_add_skips_completed_and_previously_removed():
    items = [
        {"summary": "молоко", "status": "completed"},
        {"summary": "хлеб", "status": "needs_action"},
        {"summary": "сыр", "status": "needs_action"},
        {"summary": "яйца", "status": "needs_action"},
    ]
    text = render(["сыр"])

    # молоко выполнено, сыр уже у Алисы, яйца пользователь удалил из Алисы
    assert run(tl.todo_for_add(items, text, {"яйца"})) == ["хлеб"]


def test_todo_save_syncs_both_ways():
    entity = "todo.shopping_list"
    current = [
        {"summary": "молоко", "status": "needs_action", "uid": "1"},
        {"summary": "лишний", "status": "needs_action", "uid": "2"},
    ]
    hass = FakeHass(services={entity: {entity: {"items": current}}})

    run(tl.todo_save(hass, entity, render(["молоко", "сыр"])))

    calls = [
        (service, data["item"])
        for _, service, data in hass.service_calls
        if service in ("remove_item", "add_item")
    ]
    assert ("remove_item", "2") in calls
    assert ("add_item", "сыр") in calls


# ------------------------------------------------------------ yandex_dialog --


def test_extract_returns_card_text():
    frame = {
        "directive": {
            "payload": {
                "header": {"request_id": "r1", "ref_message_id": "r1"},
                "response": {"card": {"type": "simple_text", "text": "1) хлеб"}},
            }
        }
    }

    assert YandexDialog._extract(frame, "r1") == "1) хлеб"


def test_extract_reads_cards_list():
    frame = {
        "directive": {
            "payload": {
                "header": {"ref_message_id": "r1"},
                "response": {"cards": [{"text": ""}, {"text": "готово"}]},
            }
        }
    }

    assert YandexDialog._extract(frame, "r1") == "готово"


def test_extract_skips_foreign_frames():
    frame = {
        "directive": {
            "payload": {
                "header": {"request_id": "other"},
                "response": {"card": {"text": "1) хлеб"}},
            }
        }
    }

    assert YandexDialog._extract(frame, "r1") is None


def test_extract_ignores_streaming_without_card():
    # именно этот кадр ломал синк: карточки нет, текста нет
    frame = {
        "streaming": {"source": "InitialRequest"},
        "directive": {
            "payload": {
                "header": {"request_id": "r1", "ref_message_id": "r1"},
                "response": {
                    "cards": [],
                    "directives": [{"name": "tts_play_placeholder"}],
                },
            }
        },
    }

    assert YandexDialog._extract(frame, "r1") is None


def test_extract_raises_skill_error():
    frame = {
        "directive": {
            "payload": {
                "header": {"request_id": "r1"},
                "error": {"message": "Internal error"},
            }
        }
    }

    with pytest.raises(YandexDialogError, match="Internal error"):
        YandexDialog._extract(frame, "r1")


def test_dialog_requires_device_id():
    # идентичность всегда приходит из колонки: без неё диалог не создаётся
    with pytest.raises(YandexDialogError):
        YandexDialog(session=None, device_id="", platform="cucumber")


# ------------------------------------------------ чтение списка и защита -----


class FlakyDialog(YandexDialog):
    """Первый вариант вопроса уходит в общий разговор, второй — в список."""

    def __init__(self, items: list[str]):
        self.items = list(items)
        self.asked: list[str] = []

    async def send(self, text: str, timeout: float = 25.0) -> str:
        self.asked.append(text)
        if text == QUERIES[0]:
            return "Окей, поехали."
        return render(self.items)


def test_read_list_falls_back_to_another_phrase():
    dialog = FlakyDialog(["кокос"])

    text = run(sl.read_list(dialog))

    assert "кокос" in text
    assert dialog.asked[:2] == list(QUERIES[:2])


def test_read_list_raises_when_no_phrase_works():
    class DumbDialog(YandexDialog):
        def __init__(self) -> None:
            pass

        async def send(self, text: str, timeout: float = 25.0) -> str:
            return "Окей, поехали."

    with pytest.raises(YandexDialogError):
        run(sl.read_list(DumbDialog()))


def test_read_list_accepts_explicitly_empty_list():
    class EmptyDialog(YandexDialog):
        def __init__(self) -> None:
            pass

        async def send(self, text: str, timeout: float = 25.0) -> str:
            return "В вашем списке покупок пока ничего нет."

    assert sl.looks_like_list(run(sl.read_list(EmptyDialog())))


def test_save_refuses_non_list_answer():
    data = FakeShoppingData([("молоко", False, "alice1")])
    hass = FakeHass(data)

    # именно этот ответ приходил 26.11.2026 и затирал список
    sl.shopping_save(hass, data, "Окей, поехали.")

    assert [i["name"] for i in data.items] == ["молоко"]
    assert hass.events == []


def test_save_clears_list_on_explicit_empty_answer():
    data = FakeShoppingData([("молоко", False, "alice1")])
    hass = FakeHass(data)

    sl.shopping_save(hass, data, "В вашем списке покупок пока ничего нет.")

    assert data.items == []
