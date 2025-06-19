from homeassistant.const import REQUIRED_PYTHON_VER

from custom_components.yandex_station import *
from custom_components.yandex_station.button import *
from custom_components.yandex_station.camera import *
from custom_components.yandex_station.climate import *
from custom_components.yandex_station.config_flow import *
from custom_components.yandex_station.cover import *
from custom_components.yandex_station.diagnostics import *
from custom_components.yandex_station.humidifier import *
from custom_components.yandex_station.light import *
from custom_components.yandex_station.media_player import *
from custom_components.yandex_station.notify import *
from custom_components.yandex_station.number import *
from custom_components.yandex_station.remote import *
from custom_components.yandex_station.select import *
from custom_components.yandex_station.sensor import *
from custom_components.yandex_station.switch import *
from custom_components.yandex_station.vacuum import *
from custom_components.yandex_station.water_heater import *


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
    assert YandexLight
    assert YandexStationNotificationService
    assert YandexCustomNumber
    assert YandexOther
    assert YandexEqualizer
    assert YandexCustomSensor
    assert YandexSwitch
    assert YandexVacuum
    assert YandexKettle
