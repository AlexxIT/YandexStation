from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .core.const import DOMAIN
from .core.yandex_quasar import YandexQuasar
from .hass import hass_utils


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
):
    quasar: YandexQuasar = hass.data[DOMAIN][config_entry.unique_id]

    info = get_diagnostics(hass, config_entry)
    info["device"] = quasar.devices
    return info


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
):
    did = next(did for _, did in device.identifiers)

    quasar: YandexQuasar = hass.data[DOMAIN][config_entry.unique_id]
    device = next(
        device
        for device in quasar.devices
        if device["id"] == did or device.get("quasar_info", {}).get("device_id") == did
    )

    info = get_diagnostics(hass, config_entry)
    info["device"] = device
    return info


def get_diagnostics(hass: HomeAssistant, config_entry: ConfigEntry) -> dict:
    try:
        errors = [
            entry.to_dict()
            for key, entry in hass.data["system_log"].records.items()
            if DOMAIN in str(key)
        ]
    except Exception as e:
        errors = repr(e)

    include = [
        device["id"] for _, device, _ in hass_utils.incluce_devices(hass, config_entry)
    ]

    return {"errors": errors, "include": include}
