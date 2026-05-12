import asyncio
import base64
import json
import logging
import pickle
import re
import time
from typing import Awaitable

from aiohttp import ClientResponse, ClientSession

_LOGGER = logging.getLogger(__name__)


class LoginResponse:
    def __init__(self, resp: dict):
        self.raw = resp

    @property
    def ok(self):
        return self.raw.get("status") == "ok"

    @property
    def errors(self):
        return self.raw.get("errors", [])

    @property
    def error(self):
        return self.raw["errors"][0]

    @property
    def display_login(self):
        return self.raw["display_login"]

    @property
    def x_token(self):
        return self.raw["x_token"]


class BasicSession:
    _session: ClientSession

    domain: str = None
    proxy: str = None
    ssl: bool = None

    def _request(self, method: str, url: str, **kwargs) -> Awaitable[ClientResponse]:
        """Internal request function with global support proxy ans ssl options."""
        if self.domain:
            url = url.replace("yandex.ru", self.domain)
        kwargs["proxy"] = self.proxy
        kwargs["ssl"] = self.ssl
        kwargs.setdefault("timeout", 5.0)
        return getattr(self._session, method)(url, **kwargs)

    def _get(self, url: str, **kwargs) -> Awaitable[ClientResponse]:
        return self._request("get", url, **kwargs)

    def _post(self, url: str, **kwargs) -> Awaitable[ClientResponse]:
        return self._request("post", url, **kwargs)

    @property
    def closed(self):
        return self._session.closed

    @property
    def client_session(self):
        return self._session


# noinspection PyPep8
class YandexSession(BasicSession):
    """Class for login in yandex via username, token, capcha."""

    auth_headers: dict = None
    auth_json: dict = None
    csrf_token = None

    last_ts: float = 0

    def __init__(
        self,
        session: ClientSession,
        x_token: str = None,
        music_token: str = None,
        cookie: str = None,
    ):
        """
        :param x_token: optional x-token
        :param music_token: optional token for glagol API
        :param cookie: optional base64 cookie from last session
        """
        self._session = session

        # fix bug with wrong CSRF token response
        setattr(session.cookie_jar, "_quote_cookie", False)

        self.x_token = x_token
        self.music_token = music_token
        if cookie:
            cookie_jar = session.cookie_jar
            # https://github.com/aio-libs/aiohttp/issues/7216
            _cookies = cookie_jar._cookies
            try:
                raw = base64.b64decode(cookie)
                cookie_jar._cookies = pickle.loads(raw)
                # same as CookieJar._do_expiration()
                cookie_jar.clear(lambda x: False)
            except:
                cookie_jar._cookies = _cookies

        self._update_listeners = []

    def add_update_listener(self, coro):
        """Listeners to handle automatic cookies update."""
        self._update_listeners.append(coro)

    async def get_qr(self) -> str:
        """Get link to QR-code auth."""
        r = await self._get("https://passport.yandex.ru/pwl-yandex")
        assert r.ok, r.status

        resp = await r.text()
        m = re.search(r'__CSRF__ = "([^"]+)', resp)

        self.auth_headers = {"X-CSRF-Token": m[1]}

        r = await self._post(
            "https://passport.yandex.ru/pwl-yandex/api/passport/auth/password/submit",
            json={"retpath": "https://passport.yandex.ru/"},
            headers=self.auth_headers,
        )
        assert r.ok, r.status
        self.auth_json = await r.json()

        r = await self._post(
            "https://passport.yandex.ru/pwl-yandex/api/passport/auth/magic/code",
            data={
                "location_id": "0",
                "magic_track_id": self.auth_json["track_id"],
                "track_id": "",
            },
            headers=self.auth_headers,
        )
        assert r.ok, r.status
        resp = await r.json()

        return resp["link"]

    async def login_qr(self) -> LoginResponse:
        """Check if already logged in."""
        r = await self._post(
            "https://passport.yandex.ru/pwl-yandex/api/passport/auth/magic/code/status",
            json=self.auth_json,
            headers=self.auth_headers,
        )
        assert r.ok, r.status

        resp = await r.json()
        if resp.get("state") != "otp_auth_finished":
            return LoginResponse({})

        r = await self._post(
            "https://passport.yandex.ru/pwl-yandex/api/passport/sessions/get_session",
            data={"track_id": resp["trackId"]},
            headers=self.auth_headers,
        )
        assert r.ok, r.status

        return await self.login_cookies()

    async def login_cookies(self, cookies: str = None) -> LoginResponse:
        """Support three formats:
        1. Empty - cookies will be loaded from the session
        2. JSON from Copy Cookies (Google Chrome extension)
           https://chrome.google.com/webstore/detail/copy-cookies/jcbpglbplpblnagieibnemmkiamekcdg
        3. Raw cookie string `key1=value1; key2=value2`

        For JSON format support cookies from different Yandex domains.
        """
        host = "passport.yandex.ru"
        if cookies is None:
            cookies = "; ".join(
                [
                    f"{c.key}={c.value}"
                    for c in self._session.cookie_jar
                    if c["domain"].endswith("yandex.ru")
                ]
            )
        elif cookies[0] == "[":
            # @dext0r: fix cookies auth
            raw = json.loads(cookies)
            host = next(p["domain"] for p in raw if p["domain"].startswith(".yandex."))
            cookies = "; ".join([f"{p['name']}={p['value']}" for p in raw])

        r = await self._post(
            "https://mobileproxy.passport.yandex.net/1/bundle/oauth/token_by_sessionid",
            data={
                "client_id": "c0ebe342af7d48fbbbfcf2d2eedb8f9e",
                "client_secret": "ad0a908f0aa341a182a37ecd75bc319e",
            },
            headers={"Ya-Client-Host": host, "Ya-Client-Cookie": cookies},
        )
        resp = await r.json()
        x_token = resp["access_token"]

        return await self.validate_token(x_token)

    async def validate_token(self, x_token: str) -> LoginResponse:
        """Return user info using token."""
        r = await self._get(
            "https://mobileproxy.passport.yandex.net/1/bundle/account/short_info/?avatar_size=islands-300",
            headers={"Authorization": f"OAuth {x_token}"},
        )
        resp = await r.json()
        resp["x_token"] = x_token
        return LoginResponse(resp)

    async def login_token(self, x_token: str) -> bool:
        """Login to Yandex with x-token. Usual you should'n call this method.
        Better pass your x-token to construstor and call refresh_cookies to
        check if all fine.
        """
        _LOGGER.debug("Login in Yandex with token")

        payload = {"type": "x-token", "retpath": "https://www.yandex.ru"}
        headers = {"Ya-Consumer-Authorization": f"OAuth {x_token}"}
        r = await self._post(
            "https://mobileproxy.passport.yandex.net/1/bundle/auth/x_token/",
            data=payload,
            headers=headers,
        )
        resp = await r.json()
        if resp["status"] != "ok":
            _LOGGER.error(f"Login with token error: {resp}")
            return False

        host = resp["passport_host"]
        payload = {"track_id": resp["track_id"]}
        r = await self._get(
            f"{host}/auth/session/", params=payload, allow_redirects=False
        )
        assert r.status == 302, await r.read()

        return True

    async def refresh_cookies(self) -> bool:
        """Checks if cookies ok and updates them if necessary."""
        # check cookies
        r = await self._get("https://yandex.ru/quasar?storage=1")
        resp = await r.json()
        if resp["storage"]["user"]["uid"]:
            # if cookies fine - return
            return True

        # refresh cookies
        ok = await self.login_token(self.x_token)
        if ok:
            await self._handle_update()
        return ok

    async def get_music_token(self, x_token: str):
        """Get music token using x-token. Usual you should'n call this method."""
        _LOGGER.debug("Get music token")

        payload = {
            # Thanks to https://github.com/MarshalX/yandex-music-api/
            "client_secret": "53bc75238f0c4d08a118e51fe9203300",
            "client_id": "23cabbbdc6cd418abb4b39c32c41195d",
            "grant_type": "x-token",
            "access_token": x_token,
        }
        r = await self._post("https://oauth.mobile.yandex.net/1/token", data=payload)
        resp = await r.json()
        assert "access_token" in resp, resp
        return resp["access_token"]

    async def get(self, url: str, **kwargs):
        if url.startswith(
            ("https://quasar.yandex.net/glagol/", "https://api.music.yandex.net/")
        ):
            return await self.request_glagol(url, **kwargs)
        return await self.request("get", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.request("post", url, **kwargs)

    async def put(self, url, **kwargs):
        return await self.request("put", url, **kwargs)

    async def ws_connect(self, *args, **kwargs):
        if "ssl" not in kwargs:
            kwargs.setdefault("proxy", self.proxy)
            kwargs.setdefault("ssl", self.ssl)
        return await self._session.ws_connect(*args, **kwargs)

    async def request(self, method: str, url: str, retry: int = 2, **kwargs):
        """Public request function"""
        # DDoS protection for Yandex servers
        while (delay := self.last_ts + 0.2 - time.time()) > 0:
            await asyncio.sleep(delay)
        self.last_ts = time.time()

        # all except GET should contain CSRF token
        if method != "get" and not url.startswith("https://rpc.alice.yandex.ru"):
            if self.csrf_token is None:
                _LOGGER.debug(f"Обновление CSRF-токена, proxy: {self.proxy}")
                r = await self._get(
                    "https://yandex.ru/quasar", proxy=self.proxy, ssl=self.ssl
                )
                raw = await r.text()
                m = re.search('"csrfToken2":"(.+?)"', raw)
                assert m, raw
                self.csrf_token = m[1]

            kwargs["headers"] = {"x-csrf-token": self.csrf_token}

        r = await self._request(method, url, **kwargs)
        if r.status == 200:
            return r
        elif r.status == 400:
            retry = 0
        elif r.status == 401:
            # 401 - no cookies
            await self.refresh_cookies()
        elif r.status == 403:
            # 403 - no x-csrf-token
            self.csrf_token = None
        elif not url.endswith("/get_alarms"):
            _LOGGER.warning(f"{url} return {r.status} status")

        if retry:
            _LOGGER.debug(f"Retry {method} {url}")
            return await self.request(method, url, retry - 1, **kwargs)

        raise Exception(f"{url} return {r.status} status")

    async def request_glagol(self, url: str, retry: int = 2, **kwargs):
        # update music token if needed
        if not self.music_token:
            assert self.x_token, "x-token required"
            self.music_token = await self.get_music_token(self.x_token)
            await self._handle_update()

        # OAuth should be capitalize, or music will be 128 bitrate quality
        headers = kwargs.setdefault("headers", {})
        headers["Authorization"] = f"OAuth {self.music_token}"
        r = await self._get(url, **kwargs)
        if r.status == 200:
            return r
        elif r.status == 403:
            # clear music token if problem
            self.music_token = None

        if retry:
            _LOGGER.debug(f"Retry {url}")
            return await self.request_glagol(url, retry - 1)

        raise Exception(f"{url} return {r.status} status")

    @property
    def cookie(self):
        raw = pickle.dumps(
            getattr(self._session.cookie_jar, "_cookies"), pickle.HIGHEST_PROTOCOL
        )
        return base64.b64encode(raw).decode()

    async def _handle_update(self):
        for coro in self._update_listeners:
            await coro(
                x_token=self.x_token, music_token=self.music_token, cookie=self.cookie
            )
