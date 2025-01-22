import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo

from .core.const import DOMAIN
from .core.entity import YandexCustomEntity
from .core.yandex_quasar import YandexQuasar
from .hass import hass_utils

_LOGGER = logging.getLogger(__name__)

PRESETS = {
    "off": None,
    "lessbass": [-6, 0, 0, 0, 0],
    "movie": [-3, -1, 0, 0, 3],
    "voice": [0, 0, 2, 2, 3],
    "custom": None,
    "pop": [0, 1, 2, 1, 0],
    "hiphop": [3, 2, 0, 3, 3],
    "dance": [5, 3, 0, 3, 0],
    "rock": [3, 0, -1, 2, 4],
    "electro": [3, 1, -1, 1, 2],
    "metal": [4, -2, -2, -2, 4],
    "rnb": [5, 2, -1, 2, 4],
    "classic": [0, 0, 0, 0, -3],
    "acoustics": [3, 0, 1, 1, 3],
    "jazz": [2, 0, 1, 0, 2],
    "concert": [1, 0, 0, 0, 1],
    "party": [4, 1, -2, 1, 4],
    "morebass": [5, 0, 0, 0, 0],
    "morehigh": [0, 0, 0, 0, 5],
    "morebasshigh": [5, 0, 0, 0, 5],
    "lesshigh": [0, 0, 0, 0, -5],
}

INCLUDE_CAPABILITIES = ("devices.capabilities.mode",)

EQUALIZER_PLATFORMS = (
    "cucumber",
    "chiron",
    "yandexstation",
    "yandexstation_2",
    "yandexmidi",
    "yandexmini",
    "yandexmini_2",
    "yandexmicro",
)


async def async_setup_entry(hass, entry, async_add_entities):
    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]
    async_add_entities(
        [
            YandexEqualizer(quasar, sp)
            for sp in quasar.speakers
            if sp["quasar_info"]["platform"] in EQUALIZER_PLATFORMS
        ],
        True,
    )

    entities = []

    for quasar, device, config in hass_utils.incluce_devices(hass, entry):
        if instances := config.get("capabilities"):
            for instance in device["capabilities"]:
                if instance["type"] not in INCLUDE_CAPABILITIES:
                    continue
                if instance["parameters"].get("instance", "on") in instances:
                    entities.append(YandexCustomSelect(quasar, device, instance))

    async_add_entities(entities)


# noinspection PyAbstractClass
class YandexEqualizer(SelectEntity):
    _attr_current_option: str | None = None
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:equalizer"
    _attr_options = list(PRESETS.keys())
    _attr_translation_key = "equalizer"

    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["quasar_info"]["device_id"])},
            name=self.device["name"],
        )
        self._attr_name = device["name"] + " Эквалайзер"
        self._attr_unique_id = device["quasar_info"]["device_id"] + f"_equalizer"

        self.entity_id = f"select.yandex_station_{self._attr_unique_id.lower()}"

    async def async_update(self):
        try:
            config, _ = await self.quasar.get_device_config(self.device)
            if eq := config.get("equalizer"):
                self._attr_current_option = (
                    eq["active_preset_id"] if eq["enabled"] else "off"
                )
            else:
                self._attr_current_option = None

            # выключаем автоматическое обновление
            self._attr_should_poll = False
        except Exception as e:
            _LOGGER.warning("Не удалось загрузить эквалайзер", exc_info=e)

    async def async_select_option(self, option: str):
        try:
            config, version = await self.quasar.get_device_config(self.device)

            eq: dict = config.get("equalizer")
            if not eq:
                # init default equalizer
                config["equalizer"] = eq = {
                    "bands": [
                        {"gain": 0, "freq": 60, "width": 90},
                        {"gain": 0, "freq": 230, "width": 340},
                        {"gain": 0, "freq": 910, "width": 1340},
                        {"gain": 0, "freq": 3600, "width": 5200},
                        {"gain": 0, "freq": 14000, "width": 13000},
                    ],
                    "custom_preset_bands": [0, 0, 0, 0, 0],
                    "active_preset_id": "custom",
                }

            if option != "off":
                eq["enabled"] = True
                eq["active_preset_id"] = option
                bands_gain = (
                    eq["custom_preset_bands"] if option == "custom" else PRESETS[option]
                )
                for i in range(5):
                    eq["bands"][i]["gain"] = bands_gain[i]
            else:
                eq["enabled"] = False

            await self.quasar.set_device_config(self.device, config, version)

            self._attr_current_option = option
            self._async_write_ha_state()

        except Exception as e:
            _LOGGER.warning("Не удалось изменить эквалайзер", exc_info=e)


# noinspection PyAbstractClass
class YandexCustomSelect(SelectEntity, YandexCustomEntity):
    def internal_init(self, capabilities: dict, properties: dict):
        if item := capabilities.get(self.instance):
            self._attr_options = [i["value"] for i in item["modes"]]

    def internal_update(self, capabilities: dict, properties: dict):
        if self.instance in capabilities:
            self._attr_current_option = capabilities[self.instance]

    async def async_select_option(self, option: str) -> None:
        await self.device_action(self.instance, option)
