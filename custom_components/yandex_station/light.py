from homeassistant.components.light import ColorMode, LightEntity, LightEntityFeature

from .core.entity import YandexEntity
from .hass import hass_utils

INCLUDE_TYPES = (
    "devices.types.light",
    "devices.types.light.ceiling",
    "devices.types.light.dimmable",
    "devices.types.light.garland",
    "devices.types.light.lamp",
    "devices.types.light.strip",
    "devices.types.smart_speaker.yandex.station.orion",
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
    on_instance: str = None

    def internal_init(self, capabilities: dict, properties: dict):
        self._attr_color_mode = ColorMode.ONOFF

        # backlight for Yandex Station 3 and maybe some others
        for instance in ("on", "backlight"):
            if instance in capabilities:
                self.on_instance = instance
                break

        if bright := capabilities.get("brightness"):
            self.max_brightness = bright["range"]["max"]
            self.min_brightness = bright["range"]["min"]
            self._attr_color_mode = ColorMode.BRIGHTNESS

        modes = set()

        if color := capabilities.get("color"):
            self.effects = []

            if palette := color.get("palette"):
                self.effects.extend(palette)
                modes.add(ColorMode.HS)

            if scenes := color.get("scenes"):
                self.effects.extend(scenes)

            if temp := color.get("temperature_k"):
                self._attr_max_color_temp_kelvin = temp["max"]
                self._attr_min_color_temp_kelvin = temp["min"]
                modes.add(ColorMode.COLOR_TEMP)

            if self.effects:
                self._attr_effect_list = [i["name"] for i in self.effects]
                self._attr_supported_features = LightEntityFeature.EFFECT

        self._attr_supported_color_modes = modes or {self._attr_color_mode}

    def internal_update(self, capabilities: dict, properties: dict):
        if self.on_instance in capabilities:
            self._attr_is_on = capabilities[self.on_instance]

        if "brightness" in capabilities:
            value = capabilities["brightness"]
            self._attr_brightness = (
                conv(value, self.min_brightness, self.max_brightness, 1, 255)
                if value
                else None
            )

        if animation := capabilities.get("color_animation"):
            animation_type = animation["current_animation_type"]
            if animation_type == "color":
                color = animation["animations"]["color"]
                state = color["internal_state"]
                if state["instance"] == "hsv":
                    value = state["value"]
                    self._attr_hs_color = (value["h"], value["s"])
                    self._attr_color_mode = ColorMode.HS
            elif animation_type == "scene":
                scene = animation["animations"]["scene"]
                id = scene["variant"]
                self._attr_effect = next(
                    i["name"] for i in self.effects if i["id"] == id
                )

        elif color := capabilities.get("color"):
            value = color.get("value")

            if isinstance(value, dict):
                self._attr_hs_color = (value["h"], value["s"])
                self._attr_color_mode = ColorMode.HS
            elif isinstance(value, int):
                # fix https://github.com/AlexxIT/YandexStation/issues/465
                # self._attr_hs_color = color_temperature_to_hs(value)
                self._attr_color_temp_kelvin = value
                self._attr_color_mode = ColorMode.COLOR_TEMP
            else:
                self._attr_color_temp_kelvin = None
                self._attr_hs_color = None

            if name := color.get("name"):
                self._attr_effect = name
            elif id := color.get("id"):
                self._attr_effect = next(
                    i["name"] for i in self.effects if i["id"] == id
                )
            else:
                self._attr_effect = None

    async def async_turn_on(
        self,
        brightness: int = None,
        effect: str = None,
        color_temp_kelvin: int = None,
        hs_color: tuple = None,
        **kwargs,
    ):
        if color_temp_kelvin:
            await self.device_color(temperature_k=color_temp_kelvin)
            return

        if hs_color:
            hsv = {"h": round(hs_color[0]), "s": round(hs_color[1]), "v": 100}
            await self.device_color(hsv=hsv)
            return

        payload = {}

        if brightness is not None:
            payload["brightness"] = conv(
                brightness, 1, 255, self.min_brightness, self.max_brightness
            )

        if effect is not None:
            color: dict = next(i for i in self.effects if i["name"] == effect)
            key = "color" if "value" in color else "scene"
            payload[key] = color["id"]

        if not payload:
            payload[self.on_instance] = True

        await self.device_actions(**payload)

    async def async_turn_off(self, **kwargs):
        await self.device_action(self.on_instance, False)
