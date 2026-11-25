import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.yandex_station.core import yandex_glagol

from . import FakeYandexStation


def test_local_volume_surfaces_transport_error():
    async def run():
        entity = FakeYandexStation()
        entity.local_state = {"volume": 0.5}
        entity.glagol = SimpleNamespace(send=AsyncMock(return_value={"error": "TimeoutError()"}))

        for call in (entity.async_set_volume_level(0.7), entity.async_volume_up, entity.async_volume_down):
            with pytest.raises(HomeAssistantError):
                await (call() if callable(call) else call)

        entity.glagol.send.assert_any_await({"command": "setVolume", "volume": 0.7})
        assert entity.volume_level == 0.5

    asyncio.run(run())


def test_local_volume_success_and_background_error():
    async def run():
        entity = FakeYandexStation()
        entity.local_state = {"volume": 0.5}
        entity.glagol = SimpleNamespace(send=AsyncMock(return_value={"status": "success"}))
        await entity.async_set_volume_level(0.7)
        entity.glagol.send.assert_awaited_once_with({"command": "setVolume", "volume": 0.7})

        entity.glagol.send.return_value = {"error": "TimeoutError()"}
        await entity.async_mute_volume(True, raise_on_error=False)
        entity.glagol.send.assert_awaited_with({"command": "setVolume", "volume": 0})

    asyncio.run(run())


def test_glagol_times_out_during_websocket_write(monkeypatch):
    monkeypatch.setattr(yandex_glagol, "COMMAND_TIMEOUT", 0.01, raising=False)

    async def run():
        glagol = yandex_glagol.YandexGlagol(None, {"name": "Test speaker"})

        async def never_write(_):
            await asyncio.Event().wait()

        glagol.ws = SimpleNamespace(send_json=never_write)
        result = await asyncio.wait_for(glagol.send({"command": "setVolume"}), 0.25)
        assert "error" in result
        assert not glagol.waiters

    asyncio.run(run())


def test_glagol_accepts_reply_before_write_returns():
    async def run():
        glagol = yandex_glagol.YandexGlagol(None, {"name": "Test speaker"})
        result = {"status": "success"}

        async def acknowledge(request):
            waiter = glagol.waiters.get(request["id"])
            if waiter is not None:
                waiter.set_result(result)

        glagol.ws = SimpleNamespace(send_json=acknowledge)
        assert await asyncio.wait_for(glagol.send({"command": "setVolume"}), 0.25) == result
        assert not glagol.waiters

    asyncio.run(run())


def test_glagol_cancellation_removes_pending_reply():
    async def run():
        glagol = yandex_glagol.YandexGlagol(None, {"name": "Test speaker"})
        glagol.ws = SimpleNamespace(send_json=AsyncMock())
        task = asyncio.create_task(glagol.send({"command": "setVolume"}))
        await asyncio.sleep(0)
        assert len(glagol.waiters) == 1
        try:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert not glagol.waiters
        finally:
            glagol.waiters.clear()

    asyncio.run(run())
