from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.components.vacuum import VacuumEntityFeature
from homeassistant.components.water_heater import WaterHeaterEntityFeature
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)


def test_2021_12_0():
    assert BrowseMedia
    assert MediaPlayerDeviceClass
    assert MediaPlayerEntity


def test_2022_5_0():
    assert ClimateEntityFeature
    assert HVACMode
    assert MediaPlayerEntityFeature
    assert VacuumEntityFeature
    assert WaterHeaterEntityFeature


def test_2022_10_0():
    assert MediaClass
    assert MediaType


def test_2022_11_0():
    assert UnitOfEnergy
    assert UnitOfPower
    assert UnitOfTemperature


def test_2023_1_0():
    assert UnitOfElectricCurrent
    assert UnitOfElectricPotential
