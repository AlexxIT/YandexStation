from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .core.const import DOMAIN
from .core.yandex_quasar import YandexQuasar


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]
    return {"devices": quasar.devices}


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
):
    did = next(did for _, did in device.identifiers)

    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]
    device = next(
        device
        for device in quasar.devices
        if device["id"] == did or device.get("quasar_info", {}).get("device_id") == did
    )
    return {"device": device}
