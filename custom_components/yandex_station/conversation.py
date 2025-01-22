import logging

from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationEntityFeature,
    ConversationInput,
    ConversationResult,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.intent import IntentResponse, IntentResponseErrorCode
from homeassistant.util import ulid

from .core.const import DOMAIN
from .core.yandex_quasar import YandexQuasar
from .core.yandex_station import YandexStation

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]
    async_add_entities(
        [YandexConversation(quasar, speaker) for speaker in quasar.speakers], False
    )


class YandexConversation(ConversationEntity):
    _attr_entity_registry_enabled_default = False
    _attr_supported_features = ConversationEntityFeature.CONTROL

    def __init__(self, quasar: YandexQuasar, device: dict) -> None:
        self.quasar = quasar
        self.device = device

        self._attr_name = device["name"] + " Алиса"
        self._attr_unique_id = device["quasar_info"]["device_id"] + "_conversation"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["quasar_info"]["device_id"])},
            name=self.device["name"],
        )

    @property
    def supported_languages(self) -> list[str]:
        return ["ru"]

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        response = IntentResponse(language=user_input.language)

        if user_input.conversation_id is None:
            conversation_id = ulid.ulid_now()
        else:
            try:
                ulid.ulid_to_bytes(user_input.conversation_id)
                conversation_id = ulid.ulid_now()
            except ValueError:
                conversation_id = user_input.conversation_id

        entity: YandexStation = self.device.get("entity")
        if entity and entity.glagol:
            card = await entity.glagol.send(
                {"command": "sendText", "text": user_input.text}
            )
            if card:
                if text := card.get("text"):
                    response.async_set_speech(text)
                elif error := card.get("error"):
                    response.async_set_error(
                        IntentResponseErrorCode.FAILED_TO_HANDLE, error
                    )
                else:
                    response.async_set_error(
                        IntentResponseErrorCode.NO_INTENT_MATCH, "Нет текстового ответа"
                    )
            else:
                response.async_set_error(
                    IntentResponseErrorCode.FAILED_TO_HANDLE, "Неизвестная ошибка"
                )
        else:
            response.async_set_error(
                IntentResponseErrorCode.UNKNOWN, "Алиса недоступна"
            )

        return ConversationResult(response=response, conversation_id=conversation_id)
