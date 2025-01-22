import logging

from homeassistant.components.switch import SwitchEntity

from .core.entity import YandexEntity
from .core.yandex_quasar import YandexQuasar
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = (
    "devices.types.switch",
    "devices.types.socket",
    "devices.types.ventilation",
)
INCLUDE_CAPABILITIES = ("devices.capabilities.on_off", "devices.capabilities.toggle")


async def async_setup_entry(hass, entry, async_add_entities):
    entities = []

    for quasar, device, config in hass_utils.incluce_devices(hass, entry):
        # compare device type
        if device["type"] in INCLUDE_TYPES:
            entities.append(YandexSwitch(quasar, device))

        if instances := config.get("capabilities"):
            for instance in device["capabilities"]:
                if instance["type"] not in INCLUDE_CAPABILITIES:
                    continue
                if instance["parameters"].get("instance", "on") in instances:
                    entities.append(YandexCustomSwitch(quasar, device, instance))

    async_add_entities(entities)


# noinspection PyAbstractClass
class YandexSwitch(SwitchEntity, YandexEntity):
    instance = "on"

    def internal_update(self, capabilities: dict, properties: dict):
        if self.instance in capabilities:
            self._attr_is_on = capabilities[self.instance]

    async def async_turn_on(self, **kwargs):
        await self.device_action(self.instance, True)

    async def async_turn_off(self, **kwargs):
        await self.device_action(self.instance, False)


class YandexCustomSwitch(YandexSwitch):
    def __init__(self, quasar: YandexQuasar, device: dict, config: dict):
        self.instance = config["parameters"].get("instance", "on")
        super().__init__(quasar, device)
        if name := config["parameters"].get("name"):
            self._attr_name += " " + name
        self._attr_unique_id += " " + self.instance
