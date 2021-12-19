import logging
import voluptuous as vol
from . import (
    DOMAIN,
    PLATFORMS,
    TYPE_TEXT,
    ATTR_TYPE,
    ATTR_EXTRA
)
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_ENTITY_ID, ATTR_ENTITY_ID
from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE
)
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)

from homeassistant.helpers.reload import setup_reload_service

_LOGGER = logging.getLogger(__name__)

CONF_TYPE = "type"
CONF_PREPEND_TITLE = "prepend_title"
CONF_TITLE_EFFECT = "title_effect"
SUPPORTED_EFFECTS = [
    "behind_the_wall",
    "hamster",
    "megaphone",
    "pitch_down",
    "psychodelic",
    "pulse",
    "train_announce"
]
NO_EFFECT_PREFIX = "<speaker effect=\"-\">"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ENTITY_ID): cv.entity_ids,
    vol.Optional(CONF_TYPE, default="text"): cv.string,
    vol.Optional(CONF_PREPEND_TITLE, default=True): cv.boolean,
    vol.Optional(CONF_TITLE_EFFECT): vol.All(vol.Lower, vol.In(SUPPORTED_EFFECTS))
})


def get_service(hass, config, discovery_info=None):
    """Get the Yandex Station notification service."""

    setup_reload_service(hass, DOMAIN, PLATFORMS)
    entity_id = config.get(CONF_ENTITY_ID)
    tts_type = config.get(CONF_TYPE)
    prepend_title = config.get(CONF_PREPEND_TITLE)
    title_effect = config.get(CONF_TITLE_EFFECT)
    return YandexStationNotificationService(hass, entity_id, tts_type, prepend_title, title_effect)


class YandexStationNotificationService(BaseNotificationService):
    """Implement the notification service for Yandex Station."""

    def __init__(self, hass, entity_id, tts_type, prepend_title, title_effect):
        """Initialize the service."""
        self._entity_id = entity_id
        self._type = tts_type
        self._prepend_title = prepend_title
        self._title_effect = title_effect
        self.hass = hass

    def send_message(self, message="", **kwargs):
        """Send a TTS message to the speaker."""
        title = ""
        if self._prepend_title and kwargs.get(ATTR_TITLE) is not None:
            if self._title_effect is not None:
                title = "<speaker effect=\"" + self._title_effect + "\">"

            title = title + kwargs.get(ATTR_TITLE) + " "

            if self._title_effect is not None:
                title = title + NO_EFFECT_PREFIX

        service_data = {
            ATTR_ENTITY_ID: kwargs.get(ATTR_ENTITY_ID, self._entity_id),
            ATTR_MEDIA_CONTENT_ID: title + message,
            ATTR_MEDIA_CONTENT_TYPE: self._type if self._type is not None else TYPE_TEXT
        }
        data = kwargs.get(ATTR_DATA)

        if data is not None:
            if ATTR_TYPE in data:
                service_data[ATTR_MEDIA_CONTENT_TYPE] = data.get(ATTR_TYPE)

            if ATTR_EXTRA in data:
                service_data[ATTR_EXTRA] = data.get(ATTR_EXTRA)

        return self.hass.services.call(MP_DOMAIN, SERVICE_PLAY_MEDIA, service_data)
