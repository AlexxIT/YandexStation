import asyncio
import logging
from typing import Optional

from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers.intent import IntentHandler, Intent, IntentResponse

from . import DOMAIN, DATA_SPEAKERS

_LOGGER = logging.getLogger(__name__)


async def async_setup_intents(hass: HomeAssistant) -> None:
    if DOMAIN not in hass.data:
        return

    handlers = []

    for device in hass.data[DOMAIN][DATA_SPEAKERS].values():
        platform = device['quasar_info']['platform']
        if 'host' in device or platform.startswith('yandex'):
            handler = YandexIntentHandler(device['entity'].entity_id)
            hass.helpers.intent.async_register(handler)
            handlers.append(handler)

    if not handlers:
        return

    async def listener(event: Event):
        request_id = event.data['request_id']
        for handler in handlers:
            if handler.request_id == request_id:
                handler.response_text = event.data['text']
                handler.response_waiter.set()
                return

    hass.bus.async_listen('yandex_station_response', listener)


class YandexIntentHandler(IntentHandler):
    request_id: str = None
    response_text: Optional[str] = None
    response_waiter = None

    def __init__(self, entity_id: str):
        self.intent_type = entity_id
        self.response_waiter = asyncio.Event()

        _LOGGER.debug(f"Init intent: {self.intent_type}")

    async def async_handle(self, intent: Intent) -> IntentResponse:
        self.request_id = intent.context.id
        self.response_text = None
        self.response_waiter.clear()

        await intent.hass.services.async_call('media_player', 'play_media', {
            'entity_id': self.intent_type,
            'media_content_id': intent.text_input,
            'media_content_type': 'question:' + self.request_id
        })

        await asyncio.wait_for(self.response_waiter.wait(), 2.0)

        response = intent.create_response()
        if self.response_text:
            response.async_set_speech(self.response_text)
        return response
