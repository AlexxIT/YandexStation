# Thanks to: https://github.com/iswitch/ha-yandex-icons
QUASAR_INFO: dict[str, list] = {
    # колонки Яндекса
    "yandexstation": ["yandex:station", "Яндекс", "Станция (2018)"],
    "yandexstation_2": ["yandex:station-max", "Яндекс", "Станция Макс (2020)"],
    "yandexmini": ["yandex:station-mini", "Яндекс", "Станция Мини (2019)"],
    "yandexmini_2": ["yandex:station-mini-2", "Яндекс", "Станция Мини 2 (2021)"],
    "bergamot": ["yandex:station-mini-3", "Яндекс", "Станция Мини 3 (2024)"],
    "yandexmicro": ["yandex:station-lite", "Яндекс", "Станция Лайт (2021)"],
    "plum": ["yandex:station-lite-2", "Яндекс", "Станция Лайт 2 (2024)"],
    "yandexmidi": ["yandex:station-2", "Яндекс", "Станция 2 (2022)"],  # zigbee
    "cucumber": ["yandex:station-midi", "Яндекс", "Станция Миди (2023)"],  # zigbee
    "chiron": ["yandex:station-duo-max", "Яндекс", "Станция Дуо Макс (2023)"],  # zigbee
    "orion": ["yandex:station-max", "Яндекс", "Станция 3 (2025)"],
    "mango": ["yandex:jbl-link-portable", "Яндекс", "Станция Стрит (2025)"],
    # платформа Яндекс.ТВ (без облачного управления!)
    "yandexmodule": ["yandex:module", "Яндекс", "Модуль (2019)"],
    "yandexmodule_2": ["yandex:module-2", "Яндекс", "Модуль 2 (2021)"],
    "yandex_tv": ["mdi:television-classic", "Unknown", "ТВ с Алисой"],
    # ТВ с Алисой (неизвестные модели: ТВ Станция Про QLED, ТВ Станция MiniLED)
    "goya": ["mdi:television-classic", "Яндекс", "ТВ (2022)"],
    "magritte": ["mdi:television-classic", "Яндекс", "ТВ Станция LED (2023)"],
    "magritte_2": ["mdi:television-classic", "Яндекс", "ТВ Станция QLED (2025)"],
    "monet": ["mdi:television-classic", "Яндекс", "ТВ Станция Бейсик LED (2024)"],
    "monet_2": ["mdi:television-classic", "Яндекс", "ТВ Станция Бейсик QLED (2025)"],
    "levitan": ["mdi:television-classic", "Яндекс", "ТВ Станция MiniLED (2026)"],
    "malevich": ["mdi:television-classic", "Яндекс", "ТВ Станция Про MiniLED (2025)"],
    # колонки НЕ Яндекса
    "lightcomm": ["yandex:dexp-smartbox", "DEXP", "Smartbox"],
    "elari_a98": ["yandex:elari-smartbeat", "Elari", "SmartBeat"],
    "linkplay_a98": ["yandex:irbis-a", "IRBIS", "A"],
    "wk7y": ["yandex:lg-xboom-wk7y", "LG", "XBoom AI ThinQ WK7Y"],
    "prestigio_smart_mate": ["yandex:prestigio-smartmate", "Prestigio", "Smartmate"],
    "jbl_link_music": ["yandex:jbl-link-music", "JBL", "Link Music"],
    "jbl_link_portable": ["yandex:jbl-link-portable", "JBL", "Link Portable"],
    # экран с Алисой
    "quinglong": ["yandex:display-xiaomi", "Xiaomi", "Smart Display 10R X10G (2023)"],
    # не колонки
    "saturn": ["yandex:hub", "Яндекс", "Хаб (2023)"],
    "mike": ["yandex:lg-xboom-wk7y", "Яндекс", "IP камера (2025)"],
    "cherry": ["mdi:headphones", "Яндекс", "Дропс (2026)"],
}


def has_quasar(device: dict) -> bool:
    if device.get("sharing_info"):
        return False  # skip shared devices

    if info := device.get("quasar_info"):
        if info["platform"] in {"saturn", "mike", "cherry"}:
            return False  # skip non speakers
        return True

    return False


def is_tv(device: dict) -> bool:
    if info := device.get("quasar_info"):
        return info["platform"] in {
            "goya",
            "magritte",
            "magritte_2",
            "monet",
            "monet_2",
            "levitan",
            "malevich",
        }

    return False
