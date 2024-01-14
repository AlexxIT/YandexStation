import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_INCLUDE

from .core import utils
from .core.const import DATA_CONFIG, DOMAIN
from .core.entity import YandexEntity
from .core.yandex_quasar import YandexQuasar

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = ["devices.types.switch", "devices.types.socket"]
INCLUDE_CAPABILITIES = ["devices.capabilities.on_off", "devices.capabilities.toggle"]


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]

    entities = []

    for device in quasar.devices:
        # compare device name/id/room/etc
        if not (config := utils.device_include(device, include)):
            continue

        # compare device type
        if device["type"] in INCLUDE_TYPES:
            entities.append(YandexSwitch(quasar, device))

        if not (instances := config.get("capabilities")):
            continue

        for config in device["capabilities"]:
            if utils.instance_include(config, instances, INCLUDE_CAPABILITIES):
                entities.append(YandexCustomSwitch(quasar, device, config))

    async_add_entities(entities, True)


# noinspection PyAbstractClass
class YandexSwitch(SwitchEntity, YandexEntity):
    instance = "on"

    def internal_update(self, capabilities: dict, properties: dict):
        if self.instance in capabilities:
            self._attr_is_on = capabilities[self.instance]

    async def async_turn_on(self, **kwargs):
        await self.quasar.device_action(self.device["id"], self.instance, True)

    async def async_turn_off(self, **kwargs):
        await self.quasar.device_action(self.device["id"], self.instance, False)


class YandexCustomSwitch(YandexSwitch):
    def __init__(self, quasar: YandexQuasar, device: dict, config: dict):
        self.instance = config["parameters"].get("instance", "on")
        super().__init__(quasar, device)
        if name := config["parameters"].get("name"):
            self._attr_name += " " + name
        self._attr_unique_id += " " + self.instance
