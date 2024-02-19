import logging

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .yandex_quasar import YandexQuasar

_LOGGER = logging.getLogger(__name__)


def extract_parameters(items: list[dict]) -> dict:
    result = {}
    for item in items:
        instance = item["parameters"].get("instance", "on")
        result[instance] = {"retrievable": item["retrievable"], **item["parameters"]}
    return result


def extract_state(items: list[dict]) -> dict:
    result = {}
    for item in items:
        instance = item["parameters"].get("instance", "on")
        value = item["state"]["value"] if item["state"] else None
        result[instance] = value
    return result


class YandexEntity(Entity):
    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device

        self._attr_available = device["state"] == "online"
        self._attr_name = device["name"]
        self._attr_should_poll = False
        self._attr_unique_id = device["id"].replace("-", "")

        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, device["id"])},
            name=self.device["name"],
            suggested_area=self.device.get("room_name"),
        )

        if device_info := device.get("parameters", {}).get("device_info", {}):
            for key in ("manufacturer", "model", "sw_version", "hw_version"):
                if value := device_info.get(key):
                    self._attr_device_info[key] = value

        self.internal_init(
            extract_parameters(device["capabilities"]),
            extract_parameters(device["properties"]),
        )
        self.internal_update(
            extract_state(device["capabilities"]), extract_state(device["properties"])
        )

        self.quasar.subscribe_update(device["id"], self.on_update)

    def on_update(self, device: dict):
        self._attr_available = device["state"] == "online"

        self.internal_update(
            extract_state(device["capabilities"]) if "capabilities" in device else {},
            extract_state(device["properties"]) if "properties" in device else {},
        )

        if self.hass:
            self._async_write_ha_state()

    def internal_init(self, capabilities: dict, properties: dict):
        """Will be called on Entity init. Capabilities and properties will have all variants."""
        pass

    def internal_update(self, capabilities: dict, properties: dict):
        """Will be called on Entity init and every data update. Variant
        - instance with some value (str, float, dict)
        - instance with null value
        - no instance (if it not upated)
        """
        pass

    async def async_update(self):
        device_id = self.device["id"]
        device = await self.quasar.get_device(device_id)
        self.quasar.dispatch_update(device_id, device)


class YandexCustomEntity(YandexEntity):
    def __init__(self, quasar: YandexQuasar, device: dict, config: dict):
        self.instance = config["parameters"]["instance"]
        super().__init__(quasar, device)
        self._attr_name += " " + config["parameters"]["name"]
        self._attr_unique_id += " " + self.instance
