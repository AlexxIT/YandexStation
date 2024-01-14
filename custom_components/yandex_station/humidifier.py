import logging

from homeassistant.components.humidifier import (
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.const import CONF_INCLUDE
from homeassistant.helpers.template import Template

from .core import utils
from .core.const import DATA_CONFIG, DOMAIN
from .core.entity import YandexEntity
from .core.yandex_quasar import YandexQuasar

_LOGGER = logging.getLogger(__name__)

INCLUDE_TYPES = ["devices.types.humidifier"]


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]
    entities = [
        YandexHumidifier(quasar, device, config)
        for device in quasar.devices
        if (config := utils.device_include(device, include, INCLUDE_TYPES))
    ]
    async_add_entities(entities)


# noinspection PyAbstractClass
class YandexHumidifier(HumidifierEntity, YandexEntity):
    humidity_template: Template = None
    mode_instance: str = None

    def __init__(self, quasar: YandexQuasar, device: dict, config: dict):
        super().__init__(quasar, device)
        self.config = config

    def internal_init(self, capabilities: dict, properties: dict):
        candidates = ["fan_speed", "work_speed"]

        self.mode_instance = next((i for i in candidates if i in capabilities), None)

        if item := capabilities.get("humidity"):
            self._attr_min_humidity = item["range"]["min"]
            self._attr_max_humidity = item["range"]["max"]

        if item := capabilities.get(self.mode_instance):
            self._attr_supported_features |= HumidifierEntityFeature.MODES
            self._attr_available_modes = [i["value"] for i in item["modes"]]

    def internal_update(self, capabilities: dict, properties: dict):
        if "on" in capabilities:
            self._attr_is_on = capabilities["on"]

        if "humidity" in capabilities:
            self._attr_target_humidity = capabilities["humidity"]

        if self.mode_instance in capabilities:
            self._attr_mode = capabilities[self.mode_instance]

        if self.humidity_template:
            self._attr_current_humidity = self.humidity_template.async_render()
        elif "humidity" in properties:
            self._attr_current_humidity = properties["humidity"]

    async def async_added_to_hass(self):
        if item := self.config.get("current_humidity"):
            self.humidity_template = Template(item, self.hass)

    async def async_set_humidity(self, humidity: int) -> None:
        await self.quasar.device_action(self.device["id"], "humidity", humidity)

    async def async_set_mode(self, mode: str) -> None:
        await self.quasar.device_action(self.device["id"], self.mode_instance, mode)

    async def async_turn_on(self, **kwargs):
        await self.quasar.device_action(self.device["id"], "on", True)

    async def async_turn_off(self, **kwargs):
        await self.quasar.device_action(self.device["id"], "on", False)
