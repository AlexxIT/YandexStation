from homeassistant.components.button import ButtonEntity

from .core.entity import YandexCustomEntity, YandexEntity
from .core.yandex_quasar import YandexQuasar
from .hass import hass_utils

INCLUDE_CAPABILITIES = ("devices.capabilities.custom.button",)


async def async_setup_entry(hass, entry, async_add_entities):
    entities = []

    for quasar, device, config in hass_utils.incluce_devices(hass, entry):
        # get on_off capability from intercom
        if device["type"] == "devices.types.openable.intercom":
            for instance in device["capabilities"]:
                if instance["type"] == "devices.capabilities.on_off":
                    entities.append(YandexCustomButton(quasar, device, instance))

        if device["type"] == "devices.types.camera.yandex.mike":
            entities.append(YandexCameraButton(quasar, device, "down"))
            entities.append(YandexCameraButton(quasar, device, "up"))
            entities.append(YandexCameraButton(quasar, device, "left"))
            entities.append(YandexCameraButton(quasar, device, "right"))

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


class YandexCameraButton(ButtonEntity, YandexEntity):
    def __init__(self, quasar: YandexQuasar, device: dict, direction: str):
        super().__init__(quasar, device)
        self._attr_name += " " + direction
        self._attr_unique_id += " " + direction

        if direction == "left":
            self.instance = "camera_pan"
            self.value = -1
        elif direction == "right":
            self.instance = "camera_pan"
            self.value = 1
        elif direction == "down":
            self.instance = "camera_tilt"
            self.value = -1
        elif direction == "up":
            self.instance = "camera_tilt"
            self.value = 1

    async def async_press(self) -> None:
        await self.device_action(self.instance, self.value, relative=True)
