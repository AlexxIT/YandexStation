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
    # платформа Яндекс.ТВ (без облачного управления!)
    "yandexmodule": ["yandex:module", "Яндекс", "Модуль (2019)"],
    "yandexmodule_2": ["yandex:module-2", "Яндекс", "Модуль 2 (2021)"],
    "yandex_tv": ["mdi:television-classic", "Unknown", "ТВ с Алисой"],
    # ТВ с Алисой
    "goya": ["mdi:television-classic", "Яндекс", "ТВ (2022)"],
    "magritte": ["mdi:television-classic", "Яндекс", "ТВ Станция (2023)"],
    "monet": ["mdi:television-classic", "Яндекс", "ТВ Станция Бейсик (2024)"],
    # колонки НЕ Яндекса
    "lightcomm": ["yandex:dexp-smartbox", "DEXP", "Smartbox"],
    "elari_a98": ["yandex:elari-smartbeat", "Elari", "SmartBeat"],
    "linkplay_a98": ["yandex:irbis-a", "IRBIS", "A"],
    "wk7y": ["yandex:lg-xboom-wk7y", "LG", "XBOOM AI ThinQ WK7Y"],
    "prestigio_smart_mate": ["yandex:prestigio-smartmate", "Prestigio", "Smartmate"],
    "jbl_link_music": ["yandex:jbl-link-music", "JBL", "Link Music"],
    "jbl_link_portable": ["yandex:jbl-link-portable", "JBL", "Link Portable"],
    # экран с Алисой
    "quinglong": ["yandex:display-xiaomi", "Xiaomi", "Smart Display 10R X10G (2023)"],
    # не колонки
    "saturn": ["yandex:hub", "Яндекс", "Хаб (2023)"],
    "mike": ["yandex:lg-xboom-wk7y", "Яндекс", "IP камера (2025)"],
}


def has_quasar(device: dict) -> bool:
    if device.get("sharing_info"):
        return False  # skip shared devices

    if info := device.get("quasar_info"):
        if info["platform"] in {"saturn", "mike"}:
            return False  # skip non speakers
        return True

    return False
