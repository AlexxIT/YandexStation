"""Real HA publication tests, isolated from the legacy suite's asyncio overrides."""
import asyncio
from datetime import timedelta
import logging
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import AsyncMock, patch


def test_source_discovery(scenario):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), scenario],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ != "__main__":
    import pytest

    test_source_discovery = pytest.mark.parametrize(
        "scenario", ["discovery", "configured", "hdmi", "hdmi_ready", "unload"]
    )(test_source_discovery)


async def exercise(scenario, config):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from homeassistant import bootstrap, loader
    from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature
    from homeassistant.config_entries import ConfigEntries
    from homeassistant.const import MAJOR_VERSION, MINOR_VERSION
    from homeassistant.core import HomeAssistant
    try:
        from homeassistant.core_config import DATA_CUSTOMIZE
    except ImportError:
        from homeassistant.config import DATA_CUSTOMIZE
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.entity_component import EntityComponent
    from homeassistant.helpers.entity_platform import EntityPlatform
    from homeassistant.helpers.entity_values import EntityValues
    from custom_components.yandex_station.core.const import DATA_CONFIG, DOMAIN
    from custom_components.yandex_station.core.yandex_glagol import YandexGlagol
    from custom_components.yandex_station.core.yandex_quasar import YandexQuasar
    from custom_components.yandex_station.core.yandex_station import YandexStation

    class Player(MediaPlayerEntity):
        _attr_should_poll = False
        _attr_state = "off"
        _attr_supported_features = MediaPlayerEntityFeature.PLAY_MEDIA | MediaPlayerEntityFeature.PAUSE

        def __init__(self, name):
            self._attr_name = self._attr_unique_id = name

        async def async_media_pause(self):
            self._attr_state = "paused"
            self.async_write_ha_state()

    try:
        hass = HomeAssistant(config)
    except TypeError:
        hass = HomeAssistant()
    hass.config.config_dir = config
    hass.config.skip_pip = True
    if hasattr(loader, "async_setup"):
        loader.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    await loader.async_get_custom_components(hass)
    if hasattr(bootstrap, "async_load_base_functionality"):
        await bootstrap.async_load_base_functionality(hass)
    else:
        from homeassistant.helpers import area_registry, device_registry, issue_registry
        await area_registry.async_load(hass)
        await device_registry.async_load(hass)
        await er.async_load(hass)
        await issue_registry.async_load(hass)
    logger = logging.getLogger(__name__)
    component = EntityComponent(logger, "media_player", hass)
    component.async_register_entity_service("media_pause", {}, "async_media_pause")
    settings = {"media_players": {"media_player.receiver": "HDMI"}} if scenario in (
        "configured", "hdmi", "hdmi_ready"
    ) else {}
    hass.data[DOMAIN] = {DATA_CONFIG: settings}
    hass.data[DATA_CUSTOMIZE] = EntityValues({
        "media_player.later": {"friendly_name": "Kitchen TV"},
        "media_player.receiver": {"friendly_name": "Receiver TV"},
    })
    platforms = [EntityPlatform(hass=hass, logger=logger, domain="media_player",
        platform_name=name, platform=None, scan_interval=timedelta(hours=1),
        entity_namespace=None) for name in (DOMAIN, "synthetic")]
    if hasattr(component, "_platforms"):
        for platform in platforms:
            component._platforms[platform.platform_name] = platform
    quasar = YandexQuasar(None)
    quasar.get_device_config = AsyncMock(side_effect=RuntimeError("HDMI not ready"))
    if scenario == "hdmi_ready":
        quasar.get_device_config = AsyncMock(return_value=({"hdmiAudio": False}, 1))
    quasar.set_device_config = AsyncMock()
    station = YandexStation(quasar, {
        "id": "station", "name": "Station", "capabilities": [],
        "host": "127.0.0.1", "port": 1905,
        "quasar_info": {"device_id": "station", "platform": (
            "yandexstation_2" if scenario in ("hdmi", "hdmi_ready", "unload") else "yandexmini_2"
        )},
    })

    async def add_player(name):
        await platforms[1].async_add_entities([Player(name)])
        await hass.async_block_till_done()

    def assert_tv():
        assert hass.states.get(station.entity_id).attributes["device_class"] == "tv"
        # Also check registry reflection on the current target, unlike HA 2023.2.
        if (MAJOR_VERSION, MINOR_VERSION) >= (2026, 10):
            assert er.async_get(hass).async_get(station.entity_id).original_device_class == "tv"

    with patch.object(YandexGlagol, "start_or_restart", new=AsyncMock()):
        try:
            await platforms[0].async_add_entities([station])
            station.async_set_state({"state": {"aliceState": "IDLE", "volume": 0.3}})
            registry = er.async_get(hass)
            identity = registry.async_get(station.entity_id).id
            if scenario == "discovery":
                assert not station.source_list
                assert registry.async_get(station.entity_id).original_device_class is None
                entry = registry.async_get_or_create(
                    "media_player", "synthetic", "Later", suggested_object_id="later"
                )
                registry.async_update_entity(entry.entity_id, name="Registry TV")
                hass.states.async_set(entry.entity_id, "unavailable", {
                    "restored": True, "supported_features": MediaPlayerEntityFeature.PLAY_MEDIA,
                })
                await hass.async_block_till_done()
                await add_player("Later")
                assert hass.states.get("media_player.later").name == "Kitchen TV"
                assert station.source_list == ["Станция", "Kitchen TV"]
                assert_tv()
                await station.async_select_source("Kitchen TV")
                registry.async_update_entity(station.entity_id,
                    new_entity_id="media_player.renamed_station")
                await hass.async_block_till_done()
                await add_player("Second")
                state = hass.states.get("media_player.renamed_station")
                assert state.attributes["source_list"] == ["Станция", "Kitchen TV", "Second"]
                assert state.attributes["source"] == "Kitchen TV"
                assert state.attributes["device_class"] == "tv"
                assert registry.async_get(state.entity_id).id == identity
                await station.async_remove()
                sources = list(station.source_list)
                await add_player("After removal")
                assert station.source_list == sources
            elif scenario == "unload":
                entered, release = asyncio.Event(), asyncio.Event()

                async def delayed_config(device):
                    entered.set()
                    await release.wait()
                    return {"hdmiAudio": False}, 1

                quasar.get_device_config.side_effect = delayed_config
                initialization = hass.async_create_task(station.init_local_mode())
                await entered.wait()
                await station.async_remove()
                release.set()
                await initialization
                sources = list(station.source_list or [])
                await add_player("After removal")
                assert station.source_list == sources
            else:
                await add_player("Receiver")
                assert station.source_list == ["Станция", "HDMI"]
                assert_tv()
                if scenario == "hdmi":
                    await station.async_select_source("HDMI")
                    quasar.get_device_config.side_effect = None
                    quasar.get_device_config.return_value = ({"hdmiAudio": False}, 1)
                    await station.init_local_mode()
                    assert station.source == "HDMI"
                    await station.async_select_source("Станция")
                    await station.async_select_source("HDMI")
                    assert station.hdmi_audio is False
                await station.async_select_source("HDMI")
                station.async_set_state({"state": {
                    "aliceState": "LISTENING", "volume": 0.0, "playing": False,
                    "playerState": {"hasPrev": False, "hasNext": False, "duration": 10,
                        "type": "Track", "subtitle": "", "playlistType": "Track",
                        "extra": {}, "entityInfo": {}, "id": "synthetic-track",
                        "progress": 1, "title": "Synthetic track"},
                }})
                await hass.async_block_till_done()
                assert hass.states.get("media_player.receiver").state == "paused"
                quasar.set_device_config.assert_not_awaited()
            print(f"{scenario}: passed")
        finally:
            for platform in platforms:
                await platform.async_reset()
            await hass.async_stop()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as config:
        asyncio.run(exercise(sys.argv[1], config))
