import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo

from .core.const import DOMAIN
from .core.yandex_quasar import YandexQuasar

_LOGGER = logging.getLogger(__name__)

PRESETS = [
    ["off", "Выключен"],
    ["custom", "Своя настройка"],
    ["lessbass", "Меньше басов", -6, 0, 0, 0, 0],
    ["movie", "Кино", -3, -1, 0, 0, 3],
    ["voice", "Голос", 0, 0, 2, 2, 3],
    ["pop", "Поп", 0, 1, 2, 1, 0],
    ["hiphop", "Хип-хоп", 3, 2, 0, 3, 3],
    ["dance", "Танцы", 5, 3, 0, 3, 0],
    ["rock", "Рок", 3, 0, -1, 2, 4],
    ["electro", "Электроника", 3, 1, -1, 1, 2],
    ["metal", "Метал", 4, -2, -2, -2, 4],
    ["rnb", "R’n’B", 5, 2, -1, 2, 4],
    ["classic", "Классика", 0, 0, 0, 0, -3],
    ["acoustics", "Акустика", 3, 0, 1, 1, 3],
    ["jazz", "Джаз", 2, 0, 1, 0, 2],
    ["concert", "Концерт", 1, 0, 0, 0, 1],
    ["party", "Вечеринка", 4, 1, -2, 1, 4],
    ["morebass", "Больше басов", 5, 0, 0, 0, 0],
    ["morehigh", "Больше высоких", 0, 0, 0, 0, 5],
    ["morebasshigh", "Больше басов и высоких", 5, 0, 0, 0, 5],
    ["lesshigh", "Меньше высоких", 0, 0, 0, 0, -5],
]


async def async_setup_entry(hass, entry, async_add_entities):
    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]
    async_add_entities(
        [
            YandexEqualizer(quasar, sp)
            for sp in quasar.speakers
            if sp["quasar_info"]["platform"]
            in (
                "yandexstation",
                "yandexstation_2",
                "yandexmidi",
                "yandexmini",
                "yandexmini_2",
                "yandexmicro",
            )
        ],
        True,
    )


# noinspection PyAbstractClass
class YandexEqualizer(SelectEntity):
    _attr_current_option: str = None

    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device

        self._attr_entity_registry_enabled_default = False
        self._attr_icon = "mdi:equalizer"
        self._attr_name = device["name"] + " Эквалайзер"
        self._attr_options = [i[1] for i in PRESETS]
        self._attr_unique_id = device["quasar_info"]["device_id"] + "_equalizer"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["quasar_info"]["device_id"])},
            name=self.device["name"],
        )

        self.entity_id = "media_player.yandex_station_" + self._attr_unique_id.lower()

    async def async_update(self):
        try:
            conf: dict = await self.quasar.get_device_config(self.device)
            eq = conf.get("equalizer")
            if not eq:
                return
            if not eq["enabled"]:
                eq["active_preset_id"] = "off"
            self._attr_current_option = next(
                i[1] for i in PRESETS if i[0] == eq["active_preset_id"]
            )
        except Exception as e:
            _LOGGER.warning("Не удалось загрузить эквалайзер", exc_info=e)

    async def async_select_option(self, option: str):
        try:
            conf: dict = await self.quasar.get_device_config(self.device)

            eq = conf.get("equalizer")
            if not eq:
                # init default equalizer
                conf["equalizer"] = eq = {
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

            preset = next(i for i in PRESETS if i[1] == option)
            if preset[0] != "off":
                eq["enabled"] = True
                eq["active_preset_id"] = preset[0]
                bands = (
                    eq["custom_preset_bands"] if preset[0] == "custom" else preset[2:]
                )
                for i in range(5):
                    eq["bands"][i]["gain"] = bands[i]
            else:
                eq["enabled"] = False

            await self.quasar.set_device_config(self.device, conf)

        except Exception as e:
            _LOGGER.warning("Не удалось изменить эквалайзер", exc_info=e)
