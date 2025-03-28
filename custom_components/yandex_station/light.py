from homeassistant.components.light import ColorMode, LightEntity, LightEntityFeature
from homeassistant.util.color import color_temperature_to_hs

from .core.entity import YandexEntity
from .hass import hass_utils

INCLUDE_TYPES = (
    "devices.types.light",
    "devices.types.light.ceiling",
    "devices.types.light.dimmable",
    "devices.types.light.garland",
    "devices.types.light.lamp",
    "devices.types.light.strip",
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        YandexLight(quasar, device, config)
        for quasar, device, config in hass_utils.incluce_devices(hass, entry)
        if device["type"] in INCLUDE_TYPES
    )


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
        self._attr_color_mode = ColorMode.ONOFF

        if item := capabilities.get("brightness"):
            self.max_brightness = item["range"]["max"]
            self.min_brightness = item["range"]["min"]
            self._attr_color_mode = ColorMode.BRIGHTNESS

        if item := capabilities.get("color"):
            self.effects = []

            if items := item["palette"]:
                self.effects += items
                self._attr_color_mode = ColorMode.HS

            if items := item["scenes"]:
                self.effects += items

            if self.effects:
                self._attr_effect_list = [i["name"] for i in self.effects]
                self._attr_supported_features = LightEntityFeature.EFFECT

        self._attr_supported_color_modes = {self._attr_color_mode}

    def internal_update(self, capabilities: dict, properties: dict):
        if "on" in capabilities:
            self._attr_is_on = capabilities["on"]

        if "brightness" in capabilities:
            value = capabilities["brightness"]
            self._attr_brightness = (
                conv(value, self.min_brightness, self.max_brightness, 1, 255)
                if value
                else None
            )

        # check if color exists in update
        if "color" in capabilities:
            item = capabilities["color"]
            value = item.get("value")
            if isinstance(value, dict):
                self._attr_hs_color = (value["h"], value["s"])
            elif isinstance(value, int):
                # fix https://github.com/AlexxIT/YandexStation/issues/465
                self._attr_hs_color = color_temperature_to_hs(value)
            else:
                self._attr_hs_color = None
            self._attr_effect = item["name"]

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

        await self.device_actions(**payload)

    async def async_turn_off(self, **kwargs):
        await self.device_actions(on=False)
