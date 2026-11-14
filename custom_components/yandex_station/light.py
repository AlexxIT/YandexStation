from homeassistant.components.light import ColorMode, LightEntity, LightEntityFeature

from .core.entity import YandexEntity
from .hass import hass_utils

INCLUDE_TYPES = (
    "devices.types.light",
    "devices.types.light.ceiling",
    "devices.types.light.dimmable",
    "devices.types.light.garland",
    "devices.types.light.lamp",
    "devices.types.light.sconce",
    "devices.types.light.strip",
    "devices.types.light.torchere",
    "devices.types.smart_speaker.yandex.station.orion",
)

COLOR_MUSIC_NAMES = {
    "equalizer": "Эквалайзер",
    "party": "Вечеринка",
    "gaming": "Игра",
}


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
    # Keep the last reported color_animation state to preserve saved
    # variant options when switching effects.
    animation: dict = None

    def internal_init(self, capabilities: dict, properties: dict):
        modes = set()
        self.effects = []
        # The official IoT client excludes Station 3 from animation operations.
        self.animation_uses_actions = (
            self.device["type"] == "devices.types.smart_speaker.yandex.station.orion"
        )

        # backlight for Yandex Station 3 and maybe some others
        for instance in ("on", "backlight"):
            if instance in capabilities:
                self.on_instance = instance
                modes.add(ColorMode.ONOFF)
                break

        if bright := capabilities.get("brightness"):
            self.max_brightness = bright["range"]["max"]
            self.min_brightness = bright["range"]["min"]
            modes.add(ColorMode.BRIGHTNESS)

        if color := capabilities.get("color"):
            if palette := color.get("palette"):
                self.effects.extend({**i, "animation_type": "color"} for i in palette)
                modes.add(ColorMode.HS)

            if scenes := color.get("scenes"):
                self.effects.extend({**i, "animation_type": "scene"} for i in scenes)

            if temp := color.get("temperature_k"):
                self._attr_max_color_temp_kelvin = temp["max"]
                self._attr_min_color_temp_kelvin = temp["min"]
                modes.add(ColorMode.COLOR_TEMP)

        if animation := capabilities.get("color_animation"):
            animations = animation.get("animations") or {}
            music = animations.get("color_music") or {}
            scene_ids = {
                i["id"] for i in (animations.get("scene") or {}).get("variants") or []
            }
            names = {i["name"] for i in self.effects}
            for variant in music.get("variants") or []:
                if self.animation_uses_actions and variant["id"] not in scene_ids:
                    # Station 3 also exposes musical variants as named legacy scenes.
                    scene = next(
                        (
                            i for i in self.effects
                            if i["animation_type"] == "scene" and i["id"] == variant["id"]
                        ),
                        None,
                    )
                    if scene is not None:
                        scene["animation_type"] = "color_music"
                        continue
                name = COLOR_MUSIC_NAMES.get(variant["id"], variant["id"])
                while name in names:
                    name += " (цветомузыка)"
                names.add(name)
                self.effects.append(
                    {
                        "id": variant["id"],
                        "name": name,
                        "animation_type": "color_music",
                    }
                )

        if self.effects:
            self._attr_effect_list = [i["name"] for i in self.effects]
            self._attr_supported_features = LightEntityFeature.EFFECT

        if len(modes) > 1 and ColorMode.ONOFF in modes:
            modes.remove(ColorMode.ONOFF)
        if len(modes) > 1 and ColorMode.BRIGHTNESS in modes:
            modes.remove(ColorMode.BRIGHTNESS)

        self._attr_color_mode = next(iter(modes))
        self._attr_supported_color_modes = modes

    def effect_name(self, effect_id: str, animation_type: str) -> str | None:
        return next(
            (
                i["name"]
                for i in self.effects
                if i["id"] == effect_id and i["animation_type"] == animation_type
            ),
            None,
        )

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

            if self.on_instance is None:
                self._attr_is_on = bool(self.brightness)

        if animation := capabilities.get("color_animation"):
            self.animation = animation
            animations = animation.get("animations") or {}
            animation_type = animation.get("current_animation_type")
            if animation_type == "color":
                color = animations.get("color") or {}
                state = color.get("internal_state") or {}
                if state.get("instance") == "hsv":
                    value = state["value"]
                    self._attr_hs_color = (value["h"], value["s"])
                    self._attr_color_mode = ColorMode.HS
                elif state.get("instance") == "temperature_k":
                    self._attr_color_temp_kelvin = state["value"]
                    self._attr_color_mode = ColorMode.COLOR_TEMP
                # palette color variant is the palette id
                self._attr_effect = self.effect_name(color.get("variant"), "color")
            elif animation_type in ("scene", "color_music"):
                effect = animations.get(animation_type) or {}
                self._attr_effect = self.effect_name(
                    effect.get("variant"), animation_type
                )
                self._attr_color_temp_kelvin = None
                self._attr_hs_color = None
                # Color animations still require a supported color mode when on.
                if ColorMode.HS in (self._attr_supported_color_modes or ()):
                    self._attr_color_mode = ColorMode.HS
            elif animation_type == "none":
                self._attr_effect = None

        # Mixed-capability devices report legacy color after stopping animation.
        if (not animation or animation.get("current_animation_type") == "none") and (
            color := capabilities.get("color")
        ):
            value = color.get("value")

            if isinstance(value, dict) and "h" in value:
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
                self._attr_color_mode = ColorMode.UNKNOWN

            if name := color.get("name"):
                self._attr_effect = name
            elif id := color.get("id"):
                self._attr_effect = self.effect_name(id, "color") or self.effect_name(
                    id, "scene"
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

        # turn on together with the scene/color, else backlight stays off
        if effect is not None and self.on_instance and not self.is_on:
            payload[self.on_instance] = True

        if brightness is not None:
            payload["brightness"] = conv(
                brightness, 1, 255, self.min_brightness, self.max_brightness
            )

        if effect is not None:
            color: dict = next(i for i in self.effects if i["name"] == effect)
            animation_type = color["animation_type"]
            if animation_type == "color_music" and not self.animation_uses_actions:
                animations = (self.animation or {}).get("animations") or {}
                music = animations.get("color_music") or {}
                variant = {"id": color["id"]}
                for saved in music.get("variants") or []:
                    if saved["id"] == color["id"]:
                        variant["options"] = saved.get("options") or []
                        break
                await self.device_animation("color_music", variant)
                if payload:
                    await self.device_actions(**payload)
                return

            if self.animation or animation_type == "color_music":
                # same payload as Yandex app sends for Station 3 backlight,
                # color_setting scene/color returns INTERNAL_ERROR for it
                if color["animation_type"] == "color":
                    payload["color_animation"] = {
                        "current_animation_type": "color",
                        "animations": {"color": {"variant": color["id"]}},
                    }
                else:
                    animations = (self.animation or {}).get("animations") or {}
                    saved = (animations.get(animation_type) or {}).get("variants") or []
                    variant = next((i for i in saved if i["id"] == color["id"]), None)
                    animation = {"variant": color["id"]}
                    if animation_type == "scene":
                        animation["variants"] = [
                            variant or {"id": color["id"], "options": []}
                        ]
                    elif variant is not None:
                        animation["variants"] = [{
                            "id": color["id"],
                            "options": variant.get("options") or [],
                        }]
                    payload["color_animation"] = {
                        "current_animation_type": animation_type,
                        "animations": {animation_type: animation},
                    }
            else:
                payload[color["animation_type"]] = color["id"]

        if not payload and self.on_instance:
            payload[self.on_instance] = True

        if payload:
            await self.device_actions(**payload)

    async def async_turn_off(self, **kwargs):
        if self.on_instance:
            await self.device_action(self.on_instance, False)
