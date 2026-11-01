"""Shopping-list delete sync: chunk before send, stop on a rejected retry.

Live call covered here is media_player.play_media with
media_content_type=shopping_list and media_content_id=update. That branch in
core/yandex_station.py calls hass/shopping_list.py shopping_sync, not todo_list.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LIST_QUERY = "Что в списке покупок"


def _pkg(name: str, path: Path | None = None) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__package__ = name
        module.__path__ = []
        sys.modules[name] = module
    if path is not None:
        module.__path__ = [str(path)]
    return module


def _install_stubs() -> None:
    """Import the integration modules without Home Assistant or aiohttp."""
    if "homeassistant.core" in sys.modules:
        return
    _pkg("homeassistant")
    _pkg("homeassistant.components")
    shopping = types.ModuleType("homeassistant.components.shopping_list")

    class ShoppingData:
        pass

    shopping.ShoppingData = ShoppingData
    sys.modules["homeassistant.components.shopping_list"] = shopping

    core = types.ModuleType("homeassistant.core")

    class HomeAssistant:
        pass

    core.HomeAssistant = HomeAssistant
    sys.modules["homeassistant.core"] = core

    const = types.ModuleType("homeassistant.const")
    const.EVENT_SHOPPING_LIST_UPDATED = "shopping_list_updated"
    sys.modules["homeassistant.const"] = const

    _pkg("homeassistant.helpers")
    storage = types.ModuleType("homeassistant.helpers.storage")

    class Store:
        def __init__(self, hass, version, key):
            self.hass = hass
            self.version = version
            self.key = key

        async def async_load(self):
            return getattr(self.hass, "store_data", None)

        async def async_save(self, data):
            self.hass.store_data = data
            self.hass.saved_store = data

    storage.Store = Store
    sys.modules["homeassistant.helpers.storage"] = storage

    station = ROOT / "custom_components" / "yandex_station"
    _pkg("custom_components", ROOT / "custom_components")
    _pkg("custom_components.yandex_station", station)
    _pkg("custom_components.yandex_station.core", station / "core")
    _pkg("custom_components.yandex_station.hass", station / "hass")

    glagol = types.ModuleType("custom_components.yandex_station.core.yandex_glagol")

    class YandexGlagol:
        pass

    glagol.YandexGlagol = YandexGlagol
    sys.modules["custom_components.yandex_station.core.yandex_glagol"] = glagol


_install_stubs()

from custom_components.yandex_station.hass import shopping_list as sl
from custom_components.yandex_station.hass import todo_list as tl


def alice_list(names: list[str]) -> str:
    lines = [f"{index}) {name}" for index, name in enumerate(names, 1)]
    header = f"В вашем списке покупок сейчас лежит {len(names)} товара:"
    return header + ("\n" + "\n".join(lines) if lines else "")


def command_indexes(command: str) -> list[str]:
    payload = command.removeprefix("Удали ").strip()
    if not payload:
        return []
    return [part.strip() for part in payload.split(",") if part.strip()]


def delete_commands(calls: list[dict]) -> list[str]:
    return [
        call["text"]
        for call in calls
        if call.get("command") == "sendText"
        and str(call.get("text", "")).startswith("Удали ")
    ]


class ScriptedGlagol:
    def __init__(self, on_send, delete_limit: int = 40):
        self.on_send = on_send
        self.calls: list[dict] = []
        self.delete_limit = delete_limit
        self.limit_hit = False

    async def send(self, payload: dict) -> dict:
        self.calls.append(payload)
        if len(delete_commands(self.calls)) > self.delete_limit:
            self.limit_hit = True
            return {"text": "Список покупок пуст"}
        return self.on_send(payload, self.calls)


class ShoppingHass:
    def __init__(self, items: list[dict]):
        self.data_obj = types.SimpleNamespace(
            items=items,
            save=lambda: None,
            _async_notify=lambda: None,
        )
        self.events: list[tuple] = []
        self.bus = types.SimpleNamespace(
            async_fire=lambda event, data: self.events.append((event, data))
        )
        self.executor_jobs: list = []

        def _job(fn, *args):
            self.executor_jobs.append(fn)
            return None

        self.async_add_executor_job = _job
        entry = types.SimpleNamespace(runtime_data=self.data_obj)
        self.config_entries = types.SimpleNamespace(
            async_entries=lambda domain: [entry] if domain == "shopping_list" else []
        )
        self.data: dict = {}


class TodoHass:
    def __init__(self, items: list[dict], entity_id: str):
        self.items = items
        self.entity_id = entity_id
        self.service_calls: list[tuple] = []
        self.store_data = {entity_id: [item["summary"] for item in items]}
        self.services = self

    async def async_call(self, domain, service, data, blocking=False, return_response=False):
        self.service_calls.append((domain, service, dict(data)))
        if domain == "todo" and service == "get_items":
            return {data["entity_id"]: {"items": self.items}}
        if domain == "todo" and service == "remove_item":
            uid = data.get("item")
            self.items = [
                item
                for item in self.items
                if item.get("uid") != uid and item.get("id") != uid
            ]
        return {"ok": True}


class ShoppingSyncTests(unittest.TestCase):
    def test_update_media_id_calls_shopping_list_sync(self):
        source = (
            ROOT / "custom_components" / "yandex_station" / "core" / "yandex_station.py"
        ).read_text()
        start = source.index('elif media_type == "shopping_list":')
        chunk = source[start : start + 600]
        self.assertIn('media_id == "update"', chunk)
        self.assertIn("shopping_list.shopping_sync(self.hass, self.glagol)", chunk)
        self.assertLess(
            chunk.index("shopping_list.shopping_sync"),
            chunk.index("todo_list.shopping_sync"),
        )
        self.assertLess(sl.INITIAL_REMOVE_CHUNK, 4)

    def test_more_than_four_completed_are_chunked_before_error(self):
        names = ["хлеб", "молоко", "сыр", "яйца", "чай", "кофе"]
        items = [
            {"name": name, "id": f"id-{index}", "complete": True}
            for index, name in enumerate(names)
        ]
        state = {"names": list(names)}
        oversized: list[str] = []
        not_found_seen: list[str] = []

        def on_send(payload, _calls):
            text = payload["text"]
            if text == LIST_QUERY:
                return {"text": alice_list(state["names"])}
            if text.startswith("Удали "):
                indexes = [int(part) for part in command_indexes(text)]
                if len(indexes) >= 4:
                    oversized.append(text)
                    not_found_seen.append(text)
                    return {"text": "Не найдено"}
                state["names"] = [
                    name
                    for index, name in enumerate(state["names"], 1)
                    if index not in set(indexes)
                ]
                return {"text": "Удалила"}
            raise AssertionError(text)

        hass = ShoppingHass(items)
        glagol = ScriptedGlagol(on_send)
        asyncio.run(sl.shopping_sync(hass, glagol))

        commands = delete_commands(glagol.calls)
        self.assertFalse(glagol.limit_hit)
        self.assertEqual(oversized, [])
        self.assertEqual(not_found_seen, [])
        self.assertEqual(commands, ["Удали 1, 2, 3", "Удали 1, 2, 3"])
        self.assertLess(len(command_indexes(commands[0])), 4)
        self.assertEqual(hass.data_obj.items, [])

    def test_not_found_and_unchanged_list_is_not_retried(self):
        names = ["хлеб", "молоко", "сыр", "яйца", "чай", "кофе"]
        items = [
            {"name": name, "id": f"alice{index}", "complete": True}
            for index, name in enumerate(names, 1)
        ]
        stable = alice_list(names)

        def on_send(payload, _calls):
            text = payload["text"]
            if text == LIST_QUERY:
                return {"text": stable}
            if text.startswith("Удали "):
                return {"text": "Не найдено"}
            raise AssertionError(text)

        hass = ShoppingHass(items)
        glagol = ScriptedGlagol(on_send)
        asyncio.run(sl.shopping_sync(hass, glagol))

        commands = delete_commands(glagol.calls)
        self.assertFalse(glagol.limit_hit)
        self.assertEqual(len(commands), len(set(commands)))
        self.assertLess(len(command_indexes(commands[0])), 4)
        self.assertIn("Удали 1", commands)
        self.assertEqual(
            [(item["name"], item["complete"]) for item in hass.data_obj.items],
            [(name, True) for name in names],
        )
        self.assertTrue(all(item["id"].startswith("alice") for item in hass.data_obj.items))

    def test_not_found_refresh_does_not_wipe_completed_flags(self):
        names = ["хлеб", "молоко", "сыр", "яйца", "чай"]
        items = [
            {"name": name, "id": f"alice{index}", "complete": True}
            for index, name in enumerate(names, 1)
        ]
        queries = {"count": 0}

        def on_send(payload, _calls):
            text = payload["text"]
            if text == LIST_QUERY:
                queries["count"] += 1
                if queries["count"] == 1:
                    return {"text": alice_list(names)}
                return {"text": "Не найдено"}
            if text.startswith("Удали "):
                return {"text": "Не найдено"}
            raise AssertionError(text)

        hass = ShoppingHass(items)
        glagol = ScriptedGlagol(on_send)
        asyncio.run(sl.shopping_sync(hass, glagol))

        commands = delete_commands(glagol.calls)
        self.assertGreater(len(commands), 1)
        self.assertEqual(len(commands), len(set(commands)))
        self.assertFalse(glagol.limit_hit)
        self.assertEqual(
            [(item["name"], item["complete"]) for item in hass.data_obj.items],
            [(name, True) for name in names],
        )

    def test_completed_flags_stay_for_items_alice_did_not_delete(self):
        names = ["хлеб", "молоко", "сыр", "яйца", "чай", "кофе"]
        items = [
            {"name": name, "id": f"alice{index}", "complete": True}
            for index, name in enumerate(names, 1)
        ]
        state = {"names": list(names)}

        def on_send(payload, _calls):
            text = payload["text"]
            if text == LIST_QUERY:
                return {"text": alice_list(state["names"])}
            if text.startswith("Удали "):
                indexes = [int(part) for part in command_indexes(text)]
                if state["names"] == names:
                    drop = set(indexes)
                    state["names"] = [
                        name
                        for index, name in enumerate(state["names"], 1)
                        if index not in drop
                    ]
                    return {"text": "Удалила"}
                return {"text": "Не найдено"}
            raise AssertionError(text)

        hass = ShoppingHass(items)
        glagol = ScriptedGlagol(on_send)
        asyncio.run(sl.shopping_sync(hass, glagol))

        commands = delete_commands(glagol.calls)
        self.assertFalse(glagol.limit_hit)
        self.assertLess(len(command_indexes(commands[0])), 4)
        self.assertEqual(
            [(item["name"], item["complete"]) for item in hass.data_obj.items],
            [("яйца", True), ("чай", True), ("кофе", True)],
        )

    def test_needs_action_items_are_not_selected_for_removal(self):
        names = ["молоко", "хлеб", "яйца", "сыр", "масло", "чай", "кофе", "сахар"]
        needs = {"молоко", "сыр"}
        items = []
        for index, name in enumerate(names):
            items.append(
                {
                    "name": name,
                    "id": f"id-{index}",
                    "complete": name not in needs,
                    "status": "needs_action" if name in needs else "completed",
                }
            )
        state = {"names": list(names)}
        removed: list[str] = []
        violations: list[str] = []

        def on_send(payload, _calls):
            text = payload["text"]
            if text == LIST_QUERY:
                return {"text": alice_list(state["names"])}
            if text.startswith("Удали "):
                indexes = [int(part) for part in command_indexes(text)]
                if len(indexes) > 4:
                    violations.append(text)
                chosen = [state["names"][index - 1] for index in indexes]
                if set(chosen) & needs:
                    violations.append(text)
                removed.extend(chosen)
                drop = set(indexes)
                state["names"] = [
                    name
                    for index, name in enumerate(state["names"], 1)
                    if index not in drop
                ]
                return {"text": "Удалила"}
            raise AssertionError(text)

        hass = ShoppingHass(items)
        glagol = ScriptedGlagol(on_send)
        asyncio.run(sl.shopping_sync(hass, glagol))

        self.assertEqual(violations, [])
        self.assertFalse(glagol.limit_hit)
        self.assertEqual(set(removed), set(names) - needs)
        self.assertTrue(delete_commands(glagol.calls))
        self.assertLess(len(command_indexes(delete_commands(glagol.calls)[0])), 4)
        self.assertEqual(
            [(item["name"], item["complete"]) for item in hass.data_obj.items],
            [("молоко", False), ("сыр", False)],
        )

    def test_four_and_two_rejected_singles_clear_completed(self):
        completed = ["хлеб", "молоко", "сыр", "яйца", "чай", "кофе"]
        needs = ["вода", "сок"]
        names = ["вода", *completed, "сок"]
        items = []
        for index, name in enumerate(names):
            is_need = name in needs
            items.append(
                {
                    "name": name,
                    "id": f"alice{index}",
                    "complete": not is_need,
                    "status": "needs_action" if is_need else "completed",
                }
            )
        state = {"names": list(names)}
        removed: list[str] = []

        def on_send(payload, _calls):
            text = payload["text"]
            if text == LIST_QUERY:
                return {"text": alice_list(state["names"])}
            if text.startswith("Удали "):
                indexes = [int(part) for part in command_indexes(text)]
                # Пачки 4 и 2 — в зоне сбоя. Одиночные Алиса принимает.
                if len(indexes) in (4, 2) or len(indexes) > 1:
                    return {"text": "Не найдено"}
                name = state["names"][indexes[0] - 1]
                removed.append(name)
                state["names"].pop(indexes[0] - 1)
                return {"text": "Удалила"}
            raise AssertionError(text)

        hass = ShoppingHass(items)
        glagol = ScriptedGlagol(on_send)
        asyncio.run(sl.shopping_sync(hass, glagol))

        commands = delete_commands(glagol.calls)
        four = [command for command in commands if len(command_indexes(command)) == 4]
        self.assertFalse(glagol.limit_hit)
        self.assertLess(len(command_indexes(commands[0])), 4)
        self.assertEqual(four, [])
        self.assertEqual(commands.count("Удали 2, 3, 4"), 1)
        self.assertEqual(commands.count("Удали 2, 3"), 1)
        self.assertEqual(removed, completed)
        self.assertEqual(
            [(item["name"], item["complete"]) for item in hass.data_obj.items],
            [("вода", False), ("сок", False)],
        )

    def test_rejected_single_does_not_stop_or_clear_other_flags(self):
        names = ["хлеб", "молоко", "сыр"]
        items = [
            {"name": name, "id": f"alice{index}", "complete": True}
            for index, name in enumerate(names, 1)
        ]
        state = {"names": list(names)}

        def on_send(payload, _calls):
            text = payload["text"]
            if text == LIST_QUERY:
                return {"text": alice_list(state["names"])}
            if text.startswith("Удали "):
                indexes = [int(part) for part in command_indexes(text)]
                if len(indexes) > 1:
                    return {"text": "Не найдено"}
                name = state["names"][indexes[0] - 1]
                if name == "молоко":
                    return {"text": "Не найдено"}
                state["names"].pop(indexes[0] - 1)
                return {"text": "Удалила"}
            raise AssertionError(text)

        hass = ShoppingHass(items)
        glagol = ScriptedGlagol(on_send)
        asyncio.run(sl.shopping_sync(hass, glagol))

        commands = delete_commands(glagol.calls)
        self.assertFalse(glagol.limit_hit)
        self.assertEqual(commands.count("Удали 2"), 1)
        self.assertEqual(
            [(item["name"], item["complete"]) for item in hass.data_obj.items],
            [("молоко", True)],
        )

    def test_selector_skips_incomplete_and_needs_action(self):
        data = types.SimpleNamespace(
            items=[
                {"name": "молоко", "id": "1", "complete": False},
                {"name": "хлеб", "id": "2", "complete": True},
                {
                    "name": "сыр",
                    "id": "3",
                    "complete": True,
                    "status": "needs_action",
                },
            ]
        )
        alice = alice_list(["молоко", "хлеб", "сыр"])
        self.assertEqual(sl.shopping_for_remove(data, alice), ["2"])


class TodoSyncTests(unittest.TestCase):
    def _items(self, names: list[str], completed: set[str] | None = None):
        completed = completed if completed is not None else set(names)
        return [
            {
                "summary": name,
                "uid": f"uid-{index}",
                "status": "completed" if name in completed else "needs_action",
            }
            for index, name in enumerate(names, 1)
        ]

    def test_todo_chunks_before_error_and_stops_on_not_found(self):
        names = ["хлеб", "молоко", "сыр", "яйца", "чай", "кофе"]
        items = self._items(names)
        entity_id = "todo.shopping_list"
        hass = TodoHass(items, entity_id)
        stable = alice_list(names)
        oversized: list[str] = []

        def on_send(payload, _calls):
            text = payload["text"]
            if text == LIST_QUERY:
                return {"text": stable}
            if text.startswith("Удали "):
                if len(command_indexes(text)) > 2:
                    oversized.append(text)
                return {"text": "Не найдено"}
            if text == "Стоп":
                return {"text": ""}
            raise AssertionError(text)

        glagol = ScriptedGlagol(on_send)
        asyncio.run(tl.shopping_sync(hass, glagol, entity_id))

        commands = delete_commands(glagol.calls)
        self.assertEqual(oversized, [])
        self.assertFalse(glagol.limit_hit)
        self.assertEqual(commands.count("Удали 1, 2"), 1)
        self.assertIn("Удали 1", commands)
        self.assertEqual(len(commands), len(set(commands)))
        self.assertEqual(
            [item["status"] for item in hass.items],
            ["completed"] * len(names),
        )
        removed = [
            call for call in hass.service_calls if call[1] == "remove_item"
        ]
        self.assertEqual(removed, [])

    def test_todo_needs_action_is_not_selected(self):
        names = ["молоко", "хлеб", "яйца", "сыр", "масло"]
        needs = {"молоко", "сыр"}
        items = self._items(names, completed=set(names) - needs)
        entity_id = "todo.shopping_list"
        hass = TodoHass(items, entity_id)
        state = {"names": list(names)}
        violations: list[str] = []

        def on_send(payload, _calls):
            text = payload["text"]
            if text == LIST_QUERY:
                return {"text": alice_list(state["names"])}
            if text.startswith("Удали "):
                indexes = [int(part) for part in command_indexes(text)]
                if len(indexes) > 2:
                    violations.append(text)
                chosen = [state["names"][index - 1] for index in indexes]
                if set(chosen) & needs:
                    violations.append(text)
                drop = set(indexes)
                state["names"] = [
                    name
                    for index, name in enumerate(state["names"], 1)
                    if index not in drop
                ]
                return {"text": "Удалила"}
            if text == "Стоп":
                return {"text": ""}
            raise AssertionError(text)

        glagol = ScriptedGlagol(on_send)
        asyncio.run(tl.shopping_sync(hass, glagol, entity_id))

        self.assertEqual(violations, [])
        self.assertFalse(glagol.limit_hit)
        self.assertTrue(delete_commands(glagol.calls))
        self.assertEqual(
            [(item["summary"], item["status"]) for item in hass.items],
            [("молоко", "needs_action"), ("сыр", "needs_action")],
        )

    def test_todo_progressing_list_is_still_chunked_by_two(self):
        names = ["хлеб", "молоко", "сыр", "яйца", "чай"]
        items = self._items(names)
        entity_id = "todo.shopping_list"
        hass = TodoHass(items, entity_id)
        state = {"names": list(names)}

        def on_send(payload, _calls):
            text = payload["text"]
            if text == LIST_QUERY:
                return {"text": alice_list(state["names"])}
            if text.startswith("Удали "):
                indexes = [int(part) for part in command_indexes(text)]
                if len(indexes) > 2:
                    raise AssertionError(text)
                drop = set(indexes)
                state["names"] = [
                    name
                    for index, name in enumerate(state["names"], 1)
                    if index not in drop
                ]
                return {"text": "Удалила"}
            if text == "Стоп":
                return {"text": ""}
            raise AssertionError(text)

        glagol = ScriptedGlagol(on_send)
        asyncio.run(tl.shopping_sync(hass, glagol, entity_id))
        self.assertEqual(
            delete_commands(glagol.calls),
            ["Удали 1, 2", "Удали 1, 2", "Удали 1"],
        )
        self.assertEqual(hass.items, [])

    def test_todo_rejected_chunk_falls_back_to_singles(self):
        completed = ["хлеб", "молоко", "сыр", "яйца", "чай", "кофе"]
        needs = ["вода", "сок"]
        names = ["вода", *completed, "сок"]
        items = self._items(names, completed=set(completed))
        entity_id = "todo.shopping_list"
        hass = TodoHass(items, entity_id)
        state = {"names": list(names)}
        removed: list[str] = []

        def on_send(payload, _calls):
            text = payload["text"]
            if text == LIST_QUERY:
                return {"text": alice_list(state["names"])}
            if text.startswith("Удали "):
                indexes = [int(part) for part in command_indexes(text)]
                if len(indexes) in (4, 2) or len(indexes) > 1:
                    return {"text": "Не найдено"}
                name = state["names"][indexes[0] - 1]
                removed.append(name)
                state["names"].pop(indexes[0] - 1)
                return {"text": "Удалила"}
            if text == "Стоп":
                return {"text": ""}
            raise AssertionError(text)

        glagol = ScriptedGlagol(on_send)
        asyncio.run(tl.shopping_sync(hass, glagol, entity_id))

        commands = delete_commands(glagol.calls)
        self.assertFalse(glagol.limit_hit)
        self.assertEqual(commands.count("Удали 2, 3"), 1)
        self.assertEqual(removed, completed)
        self.assertEqual(
            [(item["summary"], item["status"]) for item in hass.items],
            [("вода", "needs_action"), ("сок", "needs_action")],
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    unittest.main()
