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

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.util.ssl import SSLCipherList

from .core.const import DOMAIN
from .core.yandex_quasar import YandexQuasar
from .core.yandex_session import LoginResponse, YandexSession

_LOGGER = logging.getLogger(__name__)


def generate_qr_code(data: str) -> str:
    try:
        from homeassistant.auth.mfa_modules import totp

        # noinspection PyProtectedMember
        return totp._generate_qr_code(data)
    except Exception as e:
        return repr(e)


# noinspection PyUnusedLocal
class YandexStationFlowHandler(ConfigFlow, domain=DOMAIN):
    @property
    @lru_cache()
    def yandex(self):
        session = async_create_clientsession(
            self.hass, ssl_cipher=SSLCipherList.INTERMEDIATE
        )
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
            return await self.async_step_user()

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
                                "cookies": "Cookies",
                                "token": "Токен",
                            }
                        )
                    }
                ),
            )

        method = user_input["method"]
        if method == "qr":
            qr_url = await self.yandex.get_qr()
            return self.async_show_form(
                step_id="qr",
                description_placeholders={
                    "qr_url": qr_url,
                    "qr_data": generate_qr_code(qr_url),
                },
            )

        if method == "cookies":
            return self.async_show_form(
                step_id=method,
                data_schema=vol.Schema({vol.Required(method): str}),
                description_placeholders={
                    # hassfest prohibits the use of links in translation files
                    "ex_url": "https://chrome.google.com/webstore/detail/copy-cookies/jcbpglbplpblnagieibnemmkiamekcdg",
                    "ya_url": "https://passport.yandex.ru/profile",
                },
            )

        # cookies, token
        return self.async_show_form(
            step_id=method,
            data_schema=vol.Schema({vol.Required(method): str}),
        )

    async def async_step_qr(self, user_input):
        resp = await self.yandex.login_qr()
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

        elif resp.errors:
            _LOGGER.debug(f"Config error: {resp.error}")
            if self.cur_step:
                self.cur_step["errors"] = {"base": resp.error}
                return self.cur_step

        raise AbortFlow("not_implemented")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    @property
    def config_entry(self):
        return self.hass.config_entries.async_get_entry(self.handler)

    async def async_step_init(self, user_input: dict = None):
        if user_input:
            return self.async_create_entry(title="", data=user_input)

        quasar: YandexQuasar = self.hass.data[DOMAIN][self.config_entry.unique_id]
        devices = {i["id"]: device_name(i) for i in quasar.devices}

        # sort by names
        devices = dict(sorted(devices.items(), key=lambda x: x[1]))

        defaults = dict(self.config_entry.options)
        if include := defaults.get("include"):
            # filter only existing devices
            defaults["include"] = [i for i in include if i in devices]

        data = vol_schema({vol.Optional("include"): cv.multi_select(devices)}, defaults)
        return self.async_show_form(step_id="init", data_schema=data)


def vol_schema(schema: dict, defaults: dict | None) -> vol.Schema:
    if defaults:
        for key in schema:
            if (value := defaults.get(key.schema)) is not None:
                key.default = vol.default_factory(value)
    return vol.Schema(schema)


def device_name(device: dict) -> str:
    if room := device.get("room_name"):
        return f"{device['house_name']} - {room} - {device['name']}"
    return f"{device['house_name']} - {device['name']}"
