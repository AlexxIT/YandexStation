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
from functools import lru_cache

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from . import DOMAIN
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
    @property
    @lru_cache()
    def yandex(self):
        session = async_create_clientsession(self.hass)
        return YandexSession(session)

    async def async_step_import(self, data: dict):
        """Init by component setup. Forward YAML login/pass to auth."""
        await self.async_set_unique_id(data['username'])
        self._abort_if_unique_id_configured()

        if 'x_token' in data:
            return self.async_create_entry(
                title=data['username'],
                data={'x_token': data['x_token']})

        else:
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
        """User submited username and password. Or YAML error."""
        resp = await self.yandex.login_username(user_input['username'],
                                                user_input['password'])
        return await self._check_yandex_response(resp)

    async def async_step_cookies(self, user_input):
        resp = await self.yandex.login_cookies(user_input['cookies'])
        return await self._check_yandex_response(resp)

    async def async_step_token(self, user_input):
        resp = await self.yandex.validate_token(user_input['token'])
        return await self._check_yandex_response(resp)

    async def async_step_capcha(self, user_input):
        """User submited capcha. Or YAML error."""
        if user_input is None:
            return self.cur_step

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
                step_id='capcha',
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
