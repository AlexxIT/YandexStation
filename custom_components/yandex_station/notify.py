import voluptuous as vol
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_TYPE, \
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_EXTRA
from homeassistant.components.notify import PLATFORM_SCHEMA, ATTR_MESSAGE, \
    ATTR_DATA, BaseNotificationService
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.template import Template

from . import DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(ATTR_DATA): cv.make_entity_service_schema({
        vol.Optional(ATTR_MEDIA_CONTENT_ID): cv.template,
        vol.Optional(ATTR_MEDIA_CONTENT_TYPE, default="text"): cv.string,
        vol.Optional(ATTR_MEDIA_EXTRA): dict,
    })
})


# noinspection PyUnusedLocal
async def async_get_service(hass, config, discovery_info=None):
    """Get the Yandex Station notification service."""
    await async_setup_reload_service(hass, DOMAIN, ["notify"])

    return YandexStationNotificationService(hass, config[ATTR_DATA])


# noinspection PyAbstractClass
class YandexStationNotificationService(BaseNotificationService):
    """Implement the notification service for Yandex Station."""

    def __init__(self, hass, data: dict):
        """Initialize the service."""
        self.data = data
        self.template: Template = data.pop(ATTR_MEDIA_CONTENT_ID, None)
        if self.template:
            self.template.hass = hass

    async def async_send_message(self, message: str, **kwargs):
        """Send a TTS message to the speaker."""
        if self.template:
            kwargs[ATTR_MESSAGE] = message
            message = self.template.async_render(kwargs)

        service_data = self.data.copy()
        service_data[ATTR_MEDIA_CONTENT_ID] = message

        if kwargs.get(ATTR_DATA):
            service_data.update(kwargs[ATTR_DATA])

        return await self.hass.services.async_call(
            "media_player", "play_media", service_data
        )
