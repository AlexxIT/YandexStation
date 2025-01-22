from homeassistant.components.button import ButtonEntity

from .core.entity import YandexCustomEntity
from .hass import hass_utils

INCLUDE_CAPABILITIES = ("devices.capabilities.custom.button",)


async def async_setup_entry(hass, entry, async_add_entities):
    entities = []

    for quasar, device, config in hass_utils.incluce_devices(hass, entry):
        if instances := config.get("capabilities"):
            for instance in device["capabilities"]:
                if instance["type"] not in INCLUDE_CAPABILITIES:
                    continue
                if instance["parameters"].get("instance", "on") in instances:
                    entities.append(YandexCustomButton(quasar, device, instance))

    async_add_entities(entities)


# noinspection PyAbstractClass
class YandexCustomButton(ButtonEntity, YandexCustomEntity):
    async def async_press(self) -> None:
        await self.device_action(self.instance, True)
