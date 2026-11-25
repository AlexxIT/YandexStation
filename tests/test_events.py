import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import WSMessage, WSMsgType

import custom_components.yandex_station as integration
from custom_components.yandex_station.core.events import YandexEventTracker
from custom_components.yandex_station.core.yandex_quasar import YandexQuasar


def device(instance="motion", value="detected", activated="2026-11-25T17:25:00Z"):
    # Shape observed on a lumi.motion.agl02 and lumi.remote.b1acn02 in Quasar.
    return {
        "id": "sensor-id",
        "state": "online",
        "capabilities": [],
        "properties": [
            {
                "type": "devices.properties.event",
                "retrievable": instance == "motion",
                "reportable": True,
                "parameters": {"instance": instance},
                "state": {"instance": instance, "status": "normal", "value": value},
                "last_activated": activated,
                "last_updated": activated,
            },
            {
                "type": "devices.properties.float",
                "parameters": {"instance": "illumination"},
                "state": {"value": 3},
            },
        ],
    }


@pytest.mark.parametrize(
    "instance,value", [("motion", "detected"), ("button", "click")]
)
def test_repeated_activation_with_unchanged_value(instance, value):
    tracker = YandexEventTracker()
    assert tracker.update(device(instance, value)) == []
    for timestamp in ("2026-11-25T17:27:05Z", "2026-11-25T17:28:05Z"):
        update = device(instance, value, timestamp)
        assert tracker.update(update, live=True) == [
            {
                "device_id": "sensor-id",
                "instance": instance,
                "value": value,
                "last_activated": timestamp,
            }
        ]
        assert tracker.update(update, live=True) == []


def test_other_property_refresh_is_not_motion():
    tracker = YandexEventTracker()
    update = device()
    tracker.update(update)
    update["properties"][0]["last_updated"] = "2026-11-25T17:27:05Z"
    update["properties"][1]["state"]["value"] = 50
    assert tracker.update(update, live=True) == []


def test_reconnect_snapshot_and_out_of_order_delivery():
    tracker = YandexEventTracker()
    tracker.update(device())
    fresh = device(activated="2026-11-25T17:27:05Z")
    assert tracker.update(fresh) == []
    assert tracker.update(fresh, live=True) == []
    assert tracker.update(device(), live=True) == []
    # A delayed snapshot must not roll back the high-water mark either.
    assert tracker.update(device()) == []
    assert tracker.update(fresh, live=True) == []
    assert len(tracker.update(device(activated="2026-11-25T17:28:05Z"), live=True)) == 1


@pytest.mark.parametrize("timestamp", [None, "invalid", 123, "2026-11-25T17:28:05"])
def test_missing_or_invalid_activation_does_not_fabricate_events(timestamp):
    tracker = YandexEventTracker()
    tracker.update(device())
    update = device(activated=timestamp)
    update["properties"][0]["last_updated"] = "2026-11-25T17:28:05Z"
    assert tracker.update(update, live=True) == []


def test_first_activation_after_empty_snapshot_state():
    tracker = YandexEventTracker()
    initial = device(activated=None)
    initial["properties"][0]["state"] = None
    tracker.update(initial)
    assert len(tracker.update(device(), live=True)) == 1


def test_unknown_property_and_offline_update_are_not_events():
    tracker = YandexEventTracker()
    assert tracker.update(device(), live=True) == []
    update = device(activated="2026-11-25T17:27:05Z")
    update["state"] = "offline"
    assert tracker.update(update, live=True) == []
    update["state"] = "online"
    assert tracker.update(update, live=True) == []


def test_equivalent_timezones_and_distinct_values_in_one_second():
    tracker = YandexEventTracker()
    tracker.update(device("button", "click"))
    assert (
        tracker.update(
            device("button", "click", "2026-11-25T20:25:00+03:00"), live=True
        )
        == []
    )
    assert len(tracker.update(device("button", "double_click"), live=True)) == 1
    assert tracker.update(device("button", "click"), live=True) == []


def test_properties_and_devices_are_independent():
    tracker = YandexEventTracker()
    first = device()
    second = device()
    second["id"] = "second-sensor"
    first["properties"].append(device("button", "click")["properties"][0])
    tracker.update(first)
    tracker.update(second)
    for p in (first["properties"][0], first["properties"][2], second["properties"][0]):
        p["last_activated"] = "2026-11-25T17:27:05Z"
    assert len(tracker.update(first, live=True)) == 2
    assert len(tracker.update(second, live=True)) == 1


def test_quasar_only_dispatches_activations_from_live_messages():
    async def run():
        initial = device("button", "click")
        fresh = device("button", "click", "2026-11-25T17:26:47Z")
        duplicate = copy.deepcopy(fresh)
        duplicate["properties"][1]["state"]["value"] = 4

        async def messages():
            for update in (fresh, duplicate):
                yield WSMessage(
                    WSMsgType.TEXT,
                    json.dumps(
                        {
                            "operation": "update_states",
                            "message": json.dumps({"updated_devices": [update]}),
                        }
                    ),
                    "",
                )

        snapshot = {
            "status": "ok",
            "households": [{"all": [initial]}],
            "updates_url": "wss://example.invalid/updates",
        }
        response = SimpleNamespace(json=AsyncMock(return_value=snapshot))
        session = SimpleNamespace(
            get=AsyncMock(return_value=response),
            ws_connect=AsyncMock(return_value=messages()),
        )
        quasar = YandexQuasar(session)
        events, states = [], []
        unsubscribe = quasar.subscribe_update("event", events.append)
        quasar.subscribe_update("sensor-id", states.append)
        await quasar.connect()
        assert len(events) == 1
        assert events[0]["last_activated"] == "2026-11-25T17:26:47Z"
        assert len(states) == 3

        snapshot["households"][0]["all"] = [
            device("button", "click", "2026-11-25T17:28:00Z")
        ]
        await quasar.devices_passive_update()
        assert len(events) == 1
        assert len(states) == 4
        unsubscribe()
        quasar.dispatch_update("event", events[0])
        assert len(events) == 1

    asyncio.run(run())


def test_home_assistant_bus_respects_include_and_unloads(monkeypatch):
    async def run():
        quasar = YandexQuasar(None)
        quasar.devices = [
            {**device(), "name": "Motion", "type": "devices.types.sensor.motion"},
            {
                **device("button", "click"),
                "id": "button-id",
                "name": "Button",
                "type": "devices.types.sensor.button",
            },
        ]
        quasar.init = AsyncMock()
        quasar.start = Mock()
        session = SimpleNamespace(
            add_update_listener=Mock(), refresh_cookies=AsyncMock(return_value=True)
        )
        monkeypatch.setattr(integration, "YandexSession", Mock(return_value=session))
        monkeypatch.setattr(integration, "YandexQuasar", Mock(return_value=quasar))
        monkeypatch.setattr(integration.utils, "async_create_clientsession", Mock())
        monkeypatch.setattr(integration.hass_utils, "load_fake_devies", AsyncMock())
        monkeypatch.setattr(
            integration, "async_track_time_interval", Mock(return_value=lambda: None)
        )

        unload = []
        entry = SimpleNamespace(
            unique_id="account",
            data={},
            options={
                "include": [
                    "sensor-id",
                    {"id": "button-id", "properties": ["battery_level"]},
                ]
            },
            async_on_unload=unload.append,
            add_update_listener=Mock(return_value=lambda: None),
        )
        hass = SimpleNamespace(
            data={"yandex_station": {"config": {}, "speakers": {}}},
            bus=SimpleNamespace(async_fire=Mock()),
            config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()),
        )
        assert await integration.async_setup_entry(hass, entry)
        event = {
            "device_id": "sensor-id",
            "instance": "motion",
            "value": "detected",
            "last_activated": "2026-11-25T17:27:05Z",
        }
        quasar.dispatch_update("event", event)
        hass.bus.async_fire.assert_called_once_with("yandex_event", event)
        quasar.dispatch_update("event", {**event, "device_id": "not-included"})
        quasar.dispatch_update(
            "event", {**event, "device_id": "button-id", "instance": "button"}
        )
        assert hass.bus.async_fire.call_count == 1

        # This is also the unload order used by async_unload_entry.
        quasar.stop()
        for callback in unload:
            callback()
        quasar.dispatch_update("event", event)
        assert hass.bus.async_fire.call_count == 1

    asyncio.run(run())
