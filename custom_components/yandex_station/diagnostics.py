from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .core.const import DOMAIN
from .core.yandex_quasar import YandexQuasar


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]
    return {"devices": quasar.devices, "errors": get_errors(hass)}


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
    return {"device": device, "errors": get_errors(hass)}


def get_errors(hass: HomeAssistant) -> list | str:
    try:
        return [
            entry.to_dict()
            for key, entry in hass.data["system_log"].records.items()
            if DOMAIN in str(key)
        ]
    except Exception as e:
        return repr(e)
