"""Shopping sync regressions using the real HA imports and scoped mocks."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.yandex_station.hass import shopping_list, todo_list

from . import FakeYandexStation

QUERY = "Что в списке покупок"
BAD_CARDS = [
    None,
    {},
    {"status": "SUCCESS"},
    {"error": "TimeoutError()"},
    {"text": None},
    {"text": 42},
    {"text": ""},
    {"text": "Не найдено"},
    {"text": "Не удалось прочитать список"},
    {"text": "1) A\n3) B"},
    {"text": "1) A\n2) B\n3) "},
    {"text": "В вашем списке покупок сейчас лежит\n1) A\n2) B"},
    {"text": "В вашем списке покупок лежит 3 товара:\n1) A"},
    {"text": "В вашем списке покупок лежит 2 товара:\n1) A\n2) "},
    {"status": "ERROR", "text": "Ваш список покупок пуст."},
]


class Alice:
    def __init__(self, names):
        self.names = list(names)
        self.attempts = []
        self.reads = 0
        self.bad_at = 0
        self.bad_card = None
        self.limit = 3
        self.rejected = set()
        self.delete_reply = {"text": "Удалила"}
        self.apply_delete = True

    async def send(self, payload):
        text = payload["text"]
        if text == QUERY:
            self.reads += 1
            if self.reads == self.bad_at:
                return self.bad_card
            rows = "\n".join(f"{i}) {name}" for i, name in enumerate(self.names, 1))
            header = f"В вашем списке покупок сейчас лежит {len(self.names)} товаров:\n"
            return {"text": header + rows if rows else "Ваш список покупок пуст."}
        if text.startswith("Удали "):
            indexes = [int(i) for i in text[6:].split(",")]
            self.attempts.append((tuple(self.names), tuple(indexes)))
            chosen = {self.names[i - 1] for i in indexes}
            if len(indexes) > self.limit or chosen & self.rejected:
                return {"text": "Не найдено"}
            if self.apply_delete:
                self.names = [
                    n for i, n in enumerate(self.names, 1) if i not in indexes
                ]
            return self.delete_reply
        if text.startswith("Добавь в список покупок "):
            self.names.append(text.removeprefix("Добавь в список покупок "))
        else:
            assert text == "Стоп"
        return {"text": "Готово"}


@pytest.fixture(params=["shopping", "todo"])
def setup_sync(request, monkeypatch):
    def setup(completed=("A", "B"), active=("C",)):
        names = [*completed, *active]
        items = [
            {"name": n, "id": n, "complete": n in completed}
            if request.param == "shopping"
            else {
                "summary": n,
                "uid": n,
                "status": "completed" if n in completed else "needs_action",
            }
            for n in names
        ]
        original = deepcopy(items)
        alice = Alice(names)
        hass = Mock(data={})
        store = Mock(async_load=AsyncMock(return_value={}), async_save=AsyncMock())
        if request.param == "shopping":
            data = Mock(items=items)
            hass.config_entries.async_entries.return_value = [
                SimpleNamespace(runtime_data=data)
            ]

            def call():
                return shopping_list.shopping_sync(hass, alice)

            def saved():
                return data.items

            save_mock = hass.async_add_executor_job
        else:
            monkeypatch.setattr(todo_list, "Store", Mock(return_value=store))
            monkeypatch.setattr(
                todo_list, "get_todo_items", AsyncMock(return_value=items)
            )

            async def service(domain, action, payload, **kwargs):
                if action == "remove_item":
                    items[:] = [i for i in items if i["uid"] != payload["item"]]
                elif action == "add_item":
                    items.append({"summary": payload["item"], "status": "needs_action"})

            hass.services.async_call = AsyncMock(side_effect=service)

            def call():
                return todo_list.shopping_sync(hass, alice, "todo.shopping_list")

            def saved():
                return items

            save_mock = store.async_save
        return SimpleNamespace(
            alice=alice,
            run=lambda: asyncio.run(call()),
            items=saved,
            original=original,
            save=save_mock,
            path=request.param,
        )

    return setup


@pytest.mark.parametrize("bad", BAD_CARDS)
@pytest.mark.parametrize("read", [1, 2])
@pytest.mark.parametrize("completed", [("A",), ("A", "B")])
def test_unreadable_list_aborts_without_stale_delete_or_save(
    setup_sync, bad, read, completed
):
    ctx = setup_sync(completed=completed)
    ctx.alice.bad_at, ctx.alice.bad_card = read, bad
    with pytest.raises(HomeAssistantError):
        ctx.run()
    assert len(ctx.alice.attempts) == read - 1
    assert "C" in ctx.alice.names
    assert ctx.items() == ctx.original
    ctx.save.assert_not_called()


@pytest.mark.parametrize(
    "bad", [None, {}, {"error": "TimeoutError()"}, {"status": "ERROR"}]
)
def test_uncertain_delete_is_not_retried(setup_sync, bad):
    ctx = setup_sync()
    ctx.alice.delete_reply = bad
    with pytest.raises(HomeAssistantError):
        ctx.run()
    assert ctx.alice.names == ["C"]
    assert len(ctx.alice.attempts) == 1
    assert ctx.items() == ctx.original
    ctx.save.assert_not_called()


def test_success_without_progress_is_not_a_confirmed_rejection(setup_sync):
    ctx = setup_sync()
    ctx.alice.apply_delete = False
    with pytest.raises(HomeAssistantError, match="no progress"):
        ctx.run()
    assert len(ctx.alice.attempts) == 1
    ctx.save.assert_not_called()


@pytest.mark.parametrize("count", [0, 1, 6, 160, 161, 240, 241])
def test_chunks_and_long_lists(setup_sync, count):
    ctx = setup_sync(completed=[f"item-{i}" for i in range(count)])
    ctx.run()
    assert ctx.alice.names == ["C"]
    assert len(ctx.items()) == 1
    limit = 3 if ctx.path == "shopping" else 2
    assert len(ctx.alice.attempts) == (count + limit - 1) // limit
    assert all(len(indexes) <= limit for _, indexes in ctx.alice.attempts)


def test_confirmed_empty_list(setup_sync):
    ctx = setup_sync(active=())
    ctx.run()
    assert ctx.alice.names == []
    assert ctx.items() == []


def test_confirmed_rejection_falls_back_to_singles(setup_sync):
    ctx = setup_sync(completed=list("ABDEFG"))
    ctx.alice.limit = 1
    ctx.run()
    assert ctx.alice.names == ["C"]
    assert len(ctx.items()) == 1
    assert len(ctx.alice.attempts[0][1]) == (3 if ctx.path == "shopping" else 2)
    assert len(ctx.alice.attempts) == len(set(ctx.alice.attempts))


@pytest.mark.parametrize("rejected", [{"B"}, {"A", "B", "D"}])
def test_single_rejection_preserves_flags_and_continues(setup_sync, rejected):
    ctx = setup_sync(completed=list("ABD"))
    ctx.alice.limit, ctx.alice.rejected = 1, rejected
    with pytest.raises(HomeAssistantError, match="Some shopping list items"):
        ctx.run()
    assert set(ctx.alice.names) == rejected | {"C"}
    assert len(ctx.alice.attempts) == len(set(ctx.alice.attempts))
    assert len(ctx.alice.attempts) <= 5
    for item in ctx.items():
        if ctx.path == "shopping":
            assert item["complete"] == (item["name"] in rejected)
        else:
            assert item["status"] == (
                "completed" if item["summary"] in rejected else "needs_action"
            )
    ctx.save.assert_called_once()


@pytest.mark.parametrize("bad", BAD_CARDS)
def test_bad_refresh_after_add_does_not_clear_ha(setup_sync, bad):
    ctx = setup_sync(completed=())
    ctx.alice.names = []
    ctx.alice.bad_at, ctx.alice.bad_card = 2, bad
    with pytest.raises(HomeAssistantError):
        ctx.run()
    assert ctx.items() == ctx.original
    ctx.save.assert_not_called()


def test_update_media_id_calls_shopping_sync(monkeypatch):
    station = FakeYandexStation()
    station.local_state = {"volume": 0.2}
    station.glagol = Mock()
    shopping = AsyncMock()
    todo = AsyncMock()
    monkeypatch.setattr(shopping_list, "shopping_sync", shopping)
    monkeypatch.setattr(todo_list, "shopping_sync", todo)

    async def background(coro, name):
        return await coro

    station.hass = Mock(async_create_background_task=AsyncMock(side_effect=background))
    asyncio.run(station.async_play_media("shopping_list", "update"))
    shopping.assert_awaited_once_with(station.hass, station.glagol)
    todo.assert_not_called()
