import logging

from typing import Literal
from homeassistant.components import conversation
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import intent
from homeassistant.util import ulid

from .core.const import DOMAIN
from .core.yandex_quasar import YandexQuasar
from .core.yandex_station import YandexStation

_LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ["ru"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]

    async_add_entities(
        [
            YandexConversation(quasar, speaker)
            for speaker in await quasar.load_speakers()
        ],
        False,
    )


class YandexConversation(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """Yandex conversation agent."""

    def __init__(self, quasar: YandexQuasar, device: dict) -> None:
        super().__init__()
        self.quasar = quasar
        self.device = device

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["quasar_info"]["device_id"])},
            name=self.device["name"],
        )
        self._attr_name = device["name"] + " Алиса"
        self._attr_unique_id = device["quasar_info"]["device_id"] + "_conversation"
        self._attr_supported_features = conversation.ConversationEntityFeature.CONTROL

        self.entity_id = f"conversation.yandex_station_{self._attr_unique_id.lower()}"

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGES

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        intent_response = intent.IntentResponse(language=user_input.language)

        if user_input.conversation_id is None:
            conversation_id = ulid.ulid_now()
        else:
            try:
                ulid.ulid_to_bytes(user_input.conversation_id)
                conversation_id = ulid.ulid_now()
            except ValueError:
                conversation_id = user_input.conversation_id

        entity: YandexStation = self.device.get("entity")
        if not entity:
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Яндекс станция {self.device['quasar_info']['device_id']} не найдена",
            )
            return conversation.ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        response = self.hass.loop.create_future()

        @callback
        def event_filter(event_data):
            return (
                event_data.get("request_id") == conversation_id
                and event_data.get("entity_id") == entity.entity_id
            )

        @callback
        async def response_listener(event):
            response.set_result(event.data["text"])

        remove_listener = self.hass.bus.async_listen(
            f"{DOMAIN}_response", response_listener, event_filter
        )

        await entity.async_play_media(
            media_type=f"question:{conversation_id}", media_id=user_input.text
        )

        await response

        remove_listener()

        intent_response.async_set_speech(response.result())

        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )
