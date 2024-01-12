import asyncio

from homeassistant.core import HomeAssistant, State

from custom_components.yandex_station.core.entity import YandexEntity
from custom_components.yandex_station.core.yandex_quasar import YandexQuasar


class FakeQuasar(YandexQuasar):
    def __init__(self, data: dict):
        self.data = data

    async def get_device(self, *args):
        return self.data


def update_ha_state(cls, device: dict, **kwargs) -> State:
    asyncio.get_running_loop = lambda: asyncio.new_event_loop()

    entity: YandexEntity = cls(FakeQuasar(device), device, **kwargs)
    entity.hass = HomeAssistant("")
    entity.entity_id = "domain.object_id"

    coro = entity.async_update_ha_state(True)
    asyncio.get_event_loop().run_until_complete(coro)

    return entity.hass.states.get(entity.entity_id)


# JSON => Python
true = True
false = False
null = None
