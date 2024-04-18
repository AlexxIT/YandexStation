from homeassistant.const import REQUIRED_PYTHON_VER

from custom_components.yandex_station import *
from custom_components.yandex_station.button import YandexCustomButton
from custom_components.yandex_station.camera import YandexLyrics
from custom_components.yandex_station.climate import YandexClimate
from custom_components.yandex_station.config_flow import YandexStationFlowHandler
from custom_components.yandex_station.cover import YandexCover
from custom_components.yandex_station.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.yandex_station.humidifier import YandexHumidifier
from custom_components.yandex_station.intent import async_setup_intents
from custom_components.yandex_station.light import YandexLight
from custom_components.yandex_station.media_player import YandexIntents
from custom_components.yandex_station.notify import YandexStationNotificationService
from custom_components.yandex_station.number import YandexCustomNumber
from custom_components.yandex_station.remote import YandexOther
from custom_components.yandex_station.select import YandexEqualizer
from custom_components.yandex_station.sensor import YandexCustomSensor
from custom_components.yandex_station.switch import YandexSwitch
from custom_components.yandex_station.vacuum import YandexVacuum
from custom_components.yandex_station.water_heater import YandexKettle


def test_backward():
    # https://github.com/home-assistant/core/blob/2023.2.0/homeassistant/const.py
    assert REQUIRED_PYTHON_VER >= (3, 10, 0)

    assert async_setup_entry, async_unload_entry
    assert YandexCustomButton
    assert YandexLyrics
    assert YandexClimate
    assert YandexStationFlowHandler
    assert YandexCover
    assert async_get_config_entry_diagnostics
    assert YandexHumidifier
    assert async_setup_intents
    assert YandexLight
    assert YandexIntents
    assert YandexStationNotificationService
    assert YandexCustomNumber
    assert YandexOther
    assert YandexEqualizer
    assert YandexCustomSensor
    assert YandexSwitch
    assert YandexVacuum
    assert YandexKettle
