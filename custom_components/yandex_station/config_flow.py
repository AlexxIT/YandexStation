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
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from . import DOMAIN
from .core.yandex_session import YandexSession, LoginResponse

_LOGGER = logging.getLogger(__name__)


# noinspection PyUnusedLocal
class YandexStationFlowHandler(ConfigFlow, domain=DOMAIN):
    @property
    @lru_cache()
    def yandex(self):
        session = async_create_clientsession(self.hass)
        return YandexSession(session)

    async def async_step_import(self, data: dict):
        """Init by component setup. Forward YAML login/pass to auth."""
        await self.async_set_unique_id(data["username"])
        self._abort_if_unique_id_configured()

        if "x_token" in data:
            return self.async_create_entry(
                title=data["username"], data={"x_token": data["x_token"]}
            )

        else:
            return await self.async_step_auth(data)

    async def async_step_user(self, user_input=None):
        """Init by user via GUI"""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("method", default="qr"): vol.In(
                            {
                                "qr": "QR-код",
                                "auth": "Пароль или одноразовый ключ",
                                "email": "Ссылка на E-mail",
                                "cookies": "Cookies",
                                "token": "Токен",
                            }
                        )
                    }
                ),
            )

        method = user_input["method"]
        if method == "qr":
            return self.async_show_form(
                step_id="qr",
                description_placeholders={"qr_url": await self.yandex.get_qr()},
            )

        if method == "auth":
            return self.async_show_form(
                step_id=method,
                data_schema=vol.Schema(
                    {
                        vol.Required("username"): str,
                        vol.Required("password"): str,
                    }
                ),
            )

        if method == "email":
            return self.async_show_form(
                step_id=method,
                data_schema=vol.Schema(
                    {
                        vol.Required("username"): str,
                    }
                ),
            )

        # cookies, token
        return self.async_show_form(
            step_id=method,
            data_schema=vol.Schema(
                {
                    vol.Required(method): str,
                }
            ),
        )

    async def async_step_qr(self, user_input):
        resp = await self.yandex.login_qr()
        if not resp:
            self.cur_step["errors"] = {"base": "unauthorised"}
            return self.cur_step
        return await self._check_yandex_response(resp)

    async def async_step_auth(self, user_input):
        """User submited username and password. Or YAML error."""
        resp = await self.yandex.login_username(user_input["username"])
        if resp.ok:
            resp = await self.yandex.login_password(user_input["password"])
        return await self._check_yandex_response(resp)

    async def async_step_email(self, user_input):
        resp = await self.yandex.login_username(user_input["username"])
        if not resp.magic_link_email:
            self.cur_step["errors"] = {"base": "email.unsupported"}
            return self.cur_step

        await self.yandex.get_letter()
        return self.async_show_form(
            step_id="email2", description_placeholders={"email": resp.magic_link_email}
        )

    async def async_step_email2(self, user_input):
        resp = await self.yandex.login_letter()
        if not resp:
            self.cur_step["errors"] = {"base": "unauthorised"}
            return self.cur_step

        return await self._check_yandex_response(resp)

    async def async_step_cookies(self, user_input):
        resp = await self.yandex.login_cookies(user_input["cookies"])
        return await self._check_yandex_response(resp)

    async def async_step_token(self, user_input):
        resp = await self.yandex.validate_token(user_input["token"])
        return await self._check_yandex_response(resp)

    async def async_step_captcha(self, user_input):
        """User submited captcha. Or YAML error."""
        if user_input is None:
            return self.cur_step

        ok = await self.yandex.login_captcha(user_input["captcha_answer"])
        if not ok:
            return self.cur_step

        return self.async_show_form(
            step_id="captcha2",
            data_schema=vol.Schema(
                {
                    vol.Required("password"): str,
                }
            ),
        )

    async def async_step_captcha2(self, user_input):
        resp = await self.yandex.login_password(user_input["password"])
        return await self._check_yandex_response(resp)

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
                    entry, data={"x_token": resp.x_token}
                )
                return self.async_abort(reason="account_updated")

            else:
                # create new entry for new login
                return self.async_create_entry(
                    title=resp.display_login, data={"x_token": resp.x_token}
                )

        elif resp.error_captcha_required:
            _LOGGER.debug(f"Captcha required")
            return self.async_show_form(
                step_id="captcha",
                data_schema=vol.Schema(
                    {
                        vol.Required("captcha_answer"): str,
                    }
                ),
                description_placeholders={
                    "captcha_url": await self.yandex.get_captcha()
                },
            )

        elif resp.errors:
            _LOGGER.debug(f"Config error: {resp.error}")
            if self.cur_step:
                self.cur_step["errors"] = {"base": resp.error}
                return self.cur_step

        raise AbortFlow("not_implemented")
