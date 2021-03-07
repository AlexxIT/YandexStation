"""
1. User can enter login/pass from GUI
2. User can set login/pass in YAML
3. If the password requires updating, user need to configure another component
   with the same login.
4. Captcha will be requested if necessary
5. If authorization through YAML does not work, user can continue it through
   the GUI.
"""
import logging
from typing import Optional, Any, Mapping

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigEntry, OptionsFlow
from homeassistant.const import CONF_DEFAULT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from . import DOMAIN, CONF_CACHE_TTL, SUPPORTED_BROWSER_LANGUAGES, CONF_LANGUAGE, CONF_SHOW_HIDDEN, CONF_LYRICS, \
    CONF_MENU_OPTIONS, CONF_THUMBNAIL_RESOLUTION, CONF_MEDIA_BROWSER, CONF_WIDTH, CONF_HEIGHT
from .browse_media import BrowseTree
from .core.yandex_session import YandexSession, LoginResponse

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema({
    vol.Required('username'): str,
    vol.Required('password'): str,
})
CAPTCHA_SCHEMA = vol.Schema({
    vol.Required('captcha_answer'): str,
})


class YandexStationFlowHandler(ConfigFlow, domain=DOMAIN):
    yandex: YandexSession = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Define the config flow to handle options."""
        return YandexStationOptionsHandler(config_entry)

    async def async_step_import(self, data: dict):
        """Init by component setup. Forward YAML login/pass to auth."""
        await self.async_set_unique_id(data['username'])
        self._abort_if_unique_id_configured()

        if 'x_token' in data:
            return self.async_create_entry(
                title=data['username'],
                data={'x_token': data['x_token']})

        else:
            if self.yandex is None:
                session = async_create_clientsession(self.hass)
                self.yandex = YandexSession(session)

            return await self.async_step_auth(data)

    async def async_step_user(self, user_input=None):
        """Init by user via GUI"""
        if user_input is None:
            return self.async_show_form(
                step_id='user',
                data_schema=vol.Schema({
                    vol.Required('method', default='auth'): vol.In({
                        'auth': "Логин, пароль или одноразовый ключ",
                        'cookies': "Cookies",
                        'token': "Токен"
                    })
                })
            )

        if self.yandex is None:
            session = async_create_clientsession(self.hass)
            self.yandex = YandexSession(session)

        method = user_input['method']
        if method == 'auth':
            return self.async_show_form(
                step_id=method, data_schema=AUTH_SCHEMA
            )
        else:  # cookies, token
            return self.async_show_form(
                step_id=method, data_schema=vol.Schema({
                    vol.Required(method): str,
                })
            )

    async def async_step_auth(self, user_input):
        """User submitted username and password. Or YAML error."""
        resp = await self.yandex.login_username(user_input['username'],
                                                user_input['password'])
        return await self._check_yandex_response(resp)

    async def async_step_cookies(self, user_input):
        resp = await self.yandex.login_cookies(user_input['cookies'])
        return await self._check_yandex_response(resp)

    async def async_step_token(self, user_input):
        resp = await self.yandex.validate_token(user_input['token'])
        return await self._check_yandex_response(resp)

    async def async_step_captcha(self, user_input):
        """User submitted captcha. Or YAML error."""
        # if user_input is None:
        #     return self.cur_step

        resp = await self.yandex.login_captcha(user_input['captcha_answer'])
        return await self._check_yandex_response(resp)

    async def async_step_external(self, user_input):
        return await self.async_step_auth(user_input)

    async def _check_yandex_response(self, resp: LoginResponse):
        """Check Yandex response. Do not create entry for the same login. Show
        captcha form if captcha required. Show auth form with error if error.
        """
        if resp.ok:
            # set unique_id or return existing entry
            entry = await self.async_set_unique_id(resp.display_login)
            if entry:
                # update existing entry with same login
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={'x_token': resp.x_token}
                )
                return self.async_abort(reason='account_updated')

            else:
                # create new entry for new login
                return self.async_create_entry(
                    title=resp.display_login,
                    data={'x_token': resp.x_token})

        elif resp.captcha_image_url:
            _LOGGER.debug(f"Captcha required: {resp.captcha_image_url}")
            return self.async_show_form(
                step_id='captcha',
                data_schema=CAPTCHA_SCHEMA,
                description_placeholders={
                    'captcha_image_url': resp.captcha_image_url
                }
            )

        elif resp.external_url:
            return self.async_show_form(
                step_id='external',
                data_schema=AUTH_SCHEMA,
                description_placeholders={
                    'external_url': resp.external_url
                }
            )

        elif resp.error:
            _LOGGER.debug(f"Config error: {resp.error}")
            return self.async_show_form(
                step_id='auth',
                data_schema=AUTH_SCHEMA,
                errors={'base': resp.error}
            )

        raise NotImplemented


class YandexStationOptionsHandler(OptionsFlow):
    """Handle a Recollect Waste options flow."""

    def __init__(self, entry: ConfigEntry):
        """Initialize."""
        self._entry = entry

    @staticmethod
    def get_from_config(
            key: str,
            data_config: Optional[Mapping[str, Any]],
            options_config: Optional[Mapping[str, Any]],
            user_input: Optional[Mapping[str, Any]],
            default: Any
    ):
        if user_input is None or key not in user_input:
            if options_config is None or key not in options_config:
                if data_config is None or key not in data_config:
                    return default
                return data_config[key]
            return options_config[key]
        return user_input[key]

    def _show_form(self, user_input: Optional[dict] = None, errors: Optional[dict] = None):
        from .browse_media import YandexMusicBrowser as Browser

        _LOGGER.debug('Showing form: errors=%s, user_input=%s', errors, user_input)

        conf = (user_input or {},
                self._entry.data.get(CONF_MEDIA_BROWSER, {}),
                (self._entry.options or {}).get(CONF_MEDIA_BROWSER, {}))

        cache_ttl = int(self.get_from_config(CONF_CACHE_TTL, *conf, Browser.DEFAULT_CACHE_TTL))
        language = self.get_from_config(CONF_LANGUAGE, *conf, Browser.DEFAULT_LANGUAGE)
        show_hidden = self.get_from_config(CONF_SHOW_HIDDEN, *conf, Browser.DEFAULT_SHOW_HIDDEN)
        lyrics = self.get_from_config(CONF_LYRICS, *conf, Browser.DEFAULT_LYRICS)

        root_options = self.get_from_config(CONF_MENU_OPTIONS, *conf, None)

        if root_options is None:
            root_options = Browser.DEFAULT_MENU_OPTIONS.to_str()
        else:
            try:
                root_options = BrowseTree.from_map(root_options, validate=True)

            except (ValueError, IndexError, KeyError, TypeError):
                _LOGGER.warning('Saved menu options are invalid, showing built-in defaults')
                root_options = Browser.DEFAULT_MENU_OPTIONS

            root_options = root_options.to_str()

        thumbnail_resolution = self.get_from_config(CONF_THUMBNAIL_RESOLUTION, *conf,
                                                    Browser.DEFAULT_THUMBNAIL_RESOLUTION)
        if isinstance(thumbnail_resolution, tuple):
            thumbnail_resolution = '%dx%d' % thumbnail_resolution
        elif not isinstance(thumbnail_resolution, str):
            thumbnail_resolution = '%dx%d' % (thumbnail_resolution[CONF_WIDTH], thumbnail_resolution[CONF_HEIGHT])

        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CACHE_TTL, default=cache_ttl): int,
                    vol.Optional(CONF_LANGUAGE, default=language): vol.In(SUPPORTED_BROWSER_LANGUAGES),
                    vol.Optional(CONF_SHOW_HIDDEN, default=show_hidden): bool,
                    vol.Optional(CONF_LYRICS, default=lyrics): bool,
                    vol.Optional(CONF_MENU_OPTIONS, default=root_options): str,
                    vol.Optional(CONF_THUMBNAIL_RESOLUTION, default=thumbnail_resolution): str
                }
            ),
        )

    async def async_step_init(self, user_input: Optional[dict] = None):
        """Manage the options."""
        if user_input is not None:
            save_options = {}
            errors = {}

            # Media browser options
            from .browse_media import YandexMusicBrowser as Browser
            media_browser_options = {}

            cache_ttl = user_input.get(CONF_CACHE_TTL)
            if cache_ttl is not None and cache_ttl != Browser.DEFAULT_CACHE_TTL:
                if cache_ttl < 0:
                    errors[CONF_CACHE_TTL] = 'invalid_value_cache_ttl'
                else:
                    media_browser_options[CONF_CACHE_TTL] = cache_ttl

            language = user_input.get(CONF_LANGUAGE)
            if language is not None and language != Browser.DEFAULT_LANGUAGE:
                if language not in SUPPORTED_BROWSER_LANGUAGES:
                    # @TODO: find out if this is even possible
                    errors[CONF_LANGUAGE] = 'invalid_value_language'
                else:
                    media_browser_options[CONF_LANGUAGE] = language

            show_hidden = user_input.get(CONF_SHOW_HIDDEN)
            if show_hidden is not None and show_hidden != Browser.DEFAULT_SHOW_HIDDEN:
                media_browser_options[CONF_SHOW_HIDDEN] = show_hidden

            lyrics = user_input.get(CONF_LYRICS)
            if lyrics is not None and lyrics != Browser.DEFAULT_LYRICS:
                media_browser_options[CONF_LYRICS] = lyrics

            root_options = user_input.get(CONF_MENU_OPTIONS)
            if root_options is not None and root_options != CONF_DEFAULT:
                _LOGGER.debug('Saving root options: %s', root_options)
                try:
                    browse_tree = BrowseTree.from_str(root_options, validate=True)

                    if Browser.DEFAULT_MENU_OPTIONS != browse_tree:
                        media_browser_options[CONF_MENU_OPTIONS] = browse_tree.to_map(links_as_tuples=False)

                    _LOGGER.debug('Browse tree: %s', browse_tree)

                except (ValueError, IndexError, TypeError, TypeError) as e:
                    _LOGGER.debug('Error when saving options: %s', e)
                    errors[CONF_MENU_OPTIONS] = 'invalid_value_root_options'

            thumbnail_resolution = user_input.get(CONF_THUMBNAIL_RESOLUTION)
            if thumbnail_resolution is not None:
                thumbnail_resolution = thumbnail_resolution.split('x')
                if len(thumbnail_resolution) > 2:
                    errors[CONF_THUMBNAIL_RESOLUTION] = 'invalid_value_thumbnail_resolution'
                else:
                    try:
                        thumbnail_resolution = list(map(int, thumbnail_resolution))

                        if len(thumbnail_resolution) == 1:
                            width = height = thumbnail_resolution[0]
                        else:
                            width, height = thumbnail_resolution

                        if (width, height) != Browser.DEFAULT_THUMBNAIL_RESOLUTION:
                            media_browser_options[CONF_THUMBNAIL_RESOLUTION] = {
                                CONF_WIDTH: width,
                                CONF_HEIGHT: height
                            }
                    except ValueError:
                        errors[CONF_THUMBNAIL_RESOLUTION] = 'invalid_value_thumbnail_resolution'

            if errors:
                return self._show_form(user_input, errors=errors)

            save_options[CONF_MEDIA_BROWSER] = media_browser_options

            _LOGGER.debug('Saving options: user_input=%s, save_options=%s', user_input, save_options)

            return self.async_create_entry(title="", data=save_options)

        return self._show_form()
