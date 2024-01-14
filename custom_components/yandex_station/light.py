from homeassistant.components.light import ColorMode, LightEntity, LightEntityFeature
from homeassistant.const import CONF_INCLUDE

from .core import utils
from .core.const import DATA_CONFIG, DOMAIN
from .core.entity import YandexEntity

INCLUDE_TYPES = ["devices.types.light"]


async def async_setup_entry(hass, entry, async_add_entities):
    include = hass.data[DOMAIN][DATA_CONFIG][CONF_INCLUDE]
    quasar = hass.data[DOMAIN][entry.unique_id]
    entities = [
        YandexLight(quasar, device)
        for device in quasar.devices
        if utils.device_include(device, include, INCLUDE_TYPES)
    ]
    async_add_entities(entities, True)


def conv(value: int, src_min: int, src_max: int, dst_min: int, dst_max: int) -> int:
    value = round(
        (value - src_min) / (src_max - src_min) * (dst_max - dst_min) + dst_min
    )
    if value < dst_min:
        value = dst_min
    if value > dst_max:
        value = dst_max
    return value


# noinspection PyAbstractClass
class YandexLight(LightEntity, YandexEntity):
    max_brightness: int
    min_brightness: int
    effects: list

    def internal_init(self, capabilities: dict, properties: dict):
        self._attr_supported_color_modes = set()

        if item := capabilities.get("brightness"):
            self.max_brightness = item["range"]["max"]
            self.min_brightness = item["range"]["min"]
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)

        if item := capabilities.get("color"):
            self.effects = []

            if items := item["palette"]:
                self.effects += items
                self._attr_supported_color_modes.add(ColorMode.HS)

            if items := item["scenes"]:
                self.effects += items

            if self.effects:
                self._attr_effect_list = [i["name"] for i in self.effects]
                self._attr_supported_features = LightEntityFeature.EFFECT

    def internal_update(self, capabilities: dict, properties: dict):
        if "on" in capabilities:
            self._attr_is_on = capabilities["on"]

        if "brightness" in capabilities:
            value = capabilities["brightness"]
            self._attr_brightness = (
                conv(
                    value,
                    self.min_brightness,
                    self.max_brightness,
                    1,
                    255,
                )
                if value
                else None
            )

        # check if color exists in update
        if "color" in capabilities:
            # check if color not null
            if item := capabilities["color"]:
                self._attr_effect = item["name"]
                # check if color value exists
                if value := item.get("value"):
                    self._attr_hs_color = (value["h"], value["s"])
                else:
                    self._attr_hs_color = None
            else:
                self._attr_effect = None
                self._attr_hs_color = None

    async def async_turn_on(
        self,
        brightness: int = None,
        effect: str = None,
        hs_color: tuple = None,
        **kwargs,
    ):
        payload = {}

        if brightness is not None:
            payload["brightness"] = conv(
                brightness, 1, 255, self.min_brightness, self.max_brightness
            )

        if effect is not None:
            color: dict = next(i for i in self.effects if i["name"] == effect)
            payload["color" if "value" in color else "scene"] = color["id"]
        elif hs_color is not None:
            if colors := [color for color in self.effects if "value" in color]:
                h, s = hs_color
                # search best match (minimum diff for HS)
                color = min(
                    colors,
                    key=lambda i: abs(i["value"]["h"] - h) + abs(i["value"]["s"] - s),
                )
                payload["color"] = color["id"]

        if not payload:
            payload["on"] = True

        await self.quasar.device_actions(self.device["id"], **payload)

    async def async_turn_off(self, **kwargs):
        await self.quasar.device_actions(self.device["id"], on=False)
