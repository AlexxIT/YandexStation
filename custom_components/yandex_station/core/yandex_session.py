"""
Yandex supports base auth methods:
- password
- magic_link - auth via link to email
- sms_code - auth via pin code to mobile phone
- magic (otp?) - auth via key-app (30 seconds password)
- magic_x_token - auth via QR-conde (do not need username)

Advanced auth methods:
- x_token - auth via super-token (1 year)
- cookies - auth via cookies from passport.yandex.ru site

Errors:
- account.not_found - wrong login
- password.not_matched
- captcha.required
"""
import base64
import json
import logging
import pickle
import re

from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)


class LoginResponse:
    """"
    status: ok
       uid: 1234567890
       display_name: John
       public_name: John
       firstname: John
       lastname: McClane
       gender: m
       display_login: j0hn.mcclane
       normalized_display_login: j0hn-mcclane
       native_default_email: j0hn.mcclane@yandex.ru
       avatar_url: XXX
       is_avatar_empty: True
       public_id: XXX
       access_token: XXX
       cloud_token: XXX
       x_token: XXX
       x_token_issued_at: 1607490000
       access_token_expires_in: 24650000
       x_token_expires_in: 24650000
    status: error
       errors: [captcha.required]
       captcha_image_url: XXX
    status: error
       errors: [account.not_found]
       errors: [password.not_matched]
    """

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
        return self.raw['errors'][0]

    @property
    def display_login(self):
        return self.raw['display_login']

    @property
    def x_token(self):
        return self.raw['x_token']

    @property
    def magic_link_email(self):
        return self.raw.get("magic_link_email")

    @property
    def error_captcha_required(self):
        return "captcha.required" in self.errors


# noinspection PyPep8
class YandexSession:
    """Class for login in yandex via username, token, capcha."""
    auth_payload: dict = None
    csrf_token = None
    proxy: str = None

    def __init__(self, session: ClientSession, x_token: str = None,
                 music_token: str = None, cookie: str = None):
        """
        :param x_token: optional x-token
        :param music_token: optional token for glagol API
        :param cookie: optional base64 cookie from last session
        """
        self.session = session

        self.x_token = x_token
        self.music_token = music_token
        if cookie:
            raw = base64.b64decode(cookie)
            self.session.cookie_jar._cookies = pickle.loads(raw)

        self._update_listeners = []

    def add_update_listener(self, coro):
        """Listeners to handle automatic cookies update."""
        self._update_listeners.append(coro)

    async def login_username(self, username: str) -> LoginResponse:
        """Create login session and return supported auth methods."""
        # step 1: csrf_token
        r = await self.session.get(
            "https://passport.yandex.ru/am?app_platform=android",
            proxy=self.proxy
        )
        resp = await r.text()
        m = re.search(r'"csrf_token" value="([^"]+)"', resp)
        assert m, resp
        self.auth_payload = {"csrf_token": m[1]}

        # step 2: track_id
        r = await self.session.post(
            "https://passport.yandex.ru/registration-validations/auth/multi_step/start",
            data={**self.auth_payload, "login": username}, proxy=self.proxy
        )
        resp = await r.json()
        if resp.get("can_register") is True:
            return LoginResponse({"errors": ["account.not_found"]})

        assert resp.get("can_authorize") is True, resp
        self.auth_payload["track_id"] = resp["track_id"]

        # "preferred_auth_method":"password","auth_methods":["password","magic_link","magic_x_token"]}
        # "preferred_auth_method":"password","auth_methods":["password","sms_code","magic_x_token"]}
        # "preferred_auth_method":"magic","auth_methods":["magic","otp"]
        # "preferred_auth_method":"magic_link","auth_methods":["magic_link"]

        return LoginResponse(resp)

    async def login_password(self, password: str) -> LoginResponse:
        """Login using password or key-app (30 second password)."""
        assert self.auth_payload
        # step 3: password or 30 seconds key
        r = await self.session.post(
            "https://passport.yandex.ru/registration-validations/auth/multi_step/commit_password",
            data={
                **self.auth_payload,
                "password": password,
                "retpath": "https://passport.yandex.ru/am/finish?status=ok&from=Login"
            },
            proxy=self.proxy
        )
        resp = await r.json()
        if resp["status"] != "ok":
            return LoginResponse(resp)

        if "redirect_url" in resp:
            return LoginResponse({"errors": ["redirect.unsupported"]})

        # step 4: x_token
        return await self.login_cookies()

    async def get_qr(self) -> str:
        """Get link to QR-code auth."""
        # step 1: csrf_token
        r = await self.session.get(
            "https://passport.yandex.ru/am?app_platform=android",
            proxy=self.proxy
        )
        resp = await r.text()
        m = re.search(r'"csrf_token" value="([^"]+)"', resp)
        assert m, resp

        # step 2: track_id
        r = await self.session.post(
            "https://passport.yandex.ru/registration-validations/auth/password/submit",
            data={
                "csrf_token": m[1],
                "retpath": "https://passport.yandex.ru/profile",
                "with_code": 1,
            },
            proxy=self.proxy
        )
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        self.auth_payload = {
            "csrf_token": resp["csrf_token"],
            "track_id": resp["track_id"]
        }

        return "https://passport.yandex.ru/auth/magic/code/?track_id=" + \
               resp["track_id"]

    async def login_qr(self) -> LoginResponse:
        """Check if already logged in."""
        assert self.auth_payload
        r = await self.session.post(
            "https://passport.yandex.ru/auth/new/magic/status/",
            data=self.auth_payload, proxy=self.proxy
        )
        resp = await r.json()
        # resp={} if no auth yet
        if resp.get('status') != 'ok':
            return LoginResponse({})

        return await self.login_cookies()

    async def get_sms(self):
        """Request an SMS to user phone."""
        assert self.auth_payload
        r = await self.session.post(
            "https://passport.yandex.ru/registration-validations/phone-confirm-code-submit",
            data={**self.auth_payload, 'mode': 'tracked'}, proxy=self.proxy
        )
        resp = await r.json()
        assert resp['status'] == 'ok'

    async def login_sms(self, code: str) -> LoginResponse:
        """Login with code from SMS."""
        assert self.auth_payload
        r = await self.session.post(
            "https://passport.yandex.ru/registration-validations/phone-confirm-code",
            data={**self.auth_payload, 'mode': 'tracked', 'code': code},
            proxy=self.proxy
        )
        resp = await r.json()
        assert resp['status'] == 'ok'

        r = await self.session.post(
            "https://passport.yandex.ru/registration-validations/multi-step-commit-sms-code",
            data={
                **self.auth_payload,
                "retpath": "https://passport.yandex.ru/am/finish?status=ok&from=Login"
            },
            proxy=self.proxy
        )
        resp = await r.json()
        assert resp['status'] == 'ok'

        return await self.login_cookies()

    async def get_letter(self):
        """Request an magic link to user E-mail address."""
        assert self.auth_payload
        r = await self.session.post(
            "https://passport.yandex.ru/registration-validations/auth/send_magic_letter",
            data=self.auth_payload, proxy=self.proxy
        )
        resp = await r.json()
        assert resp['status'] == 'ok'

    async def login_letter(self) -> LoginResponse:
        """Check if already logged in."""
        assert self.auth_payload
        r = await self.session.post(
            "https://passport.yandex.ru/auth/letter/status/",
            data=self.auth_payload, proxy=self.proxy
        )
        resp = await r.json()
        assert resp['status'] == 'ok'
        if not resp['magic_link_confirmed']:
            return LoginResponse({})

        return await self.login_cookies()

    async def get_captcha(self) -> str:
        """Get link to captcha image."""
        assert self.auth_payload
        r = await self.session.post(
            "https://passport.yandex.ru/registration-validations/textcaptcha",
            data=self.auth_payload,
            headers={"X-Requested-With": "XMLHttpRequest"},
            proxy=self.proxy
        )
        resp = await r.json()
        assert resp['status'] == 'ok'
        self.auth_payload["key"] = resp["key"]
        return resp["image_url"]

    async def login_captcha(self, captcha_answer: str) -> bool:
        """Login with answer to captcha from login_username."""
        _LOGGER.debug("Login in Yandex with captcha")
        assert self.auth_payload
        r = await self.session.post(
            "https://passport.yandex.ru/registration-validations/checkHuman",
            data={**self.auth_payload, "answer": captcha_answer},
            headers={"X-Requested-With": "XMLHttpRequest"},
            proxy=self.proxy
        )
        resp = await r.json()
        return resp['status'] == 'ok'

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
            cookies = "; ".join([
                f"{c.key}={c.value}" for c in self.session.cookie_jar
                if c["domain"].endswith("yandex.ru")
            ])
        elif cookies[0] == "[":
            raw = json.loads(cookies)
            host = next(
                p["domain"] for p in raw
                if p["domain"].startswith("passport.yandex.")
            )
            cookies = "; ".join([f"{p['name']}={p['value']}" for p in raw])

        r = await self.session.post(
            "https://mobileproxy.passport.yandex.net/1/bundle/oauth/token_by_sessionid",
            data={
                "client_id": "c0ebe342af7d48fbbbfcf2d2eedb8f9e",
                "client_secret": "ad0a908f0aa341a182a37ecd75bc319e",
            }, headers={
                "Ya-Client-Host": host,
                "Ya-Client-Cookie": cookies
            },
            proxy=self.proxy
        )
        resp = await r.json()
        x_token = resp["access_token"]

        return await self.validate_token(x_token)

    async def validate_token(self, x_token: str) -> LoginResponse:
        """Return user info using token."""
        r = await self.session.get(
            "https://mobileproxy.passport.yandex.net/1/bundle/account/short_info/?avatar_size=islands-300",
            headers={'Authorization': f"OAuth {x_token}"}, proxy=self.proxy
        )
        resp = await r.json()
        resp['x_token'] = x_token
        return LoginResponse(resp)

    async def login_token(self, x_token: str) -> bool:
        """Login to Yandex with x-token. Usual you should'n call this method.
        Better pass your x-token to construstor and call refresh_cookies to
        check if all fine.
        """
        _LOGGER.debug("Login in Yandex with token")

        payload = {
            'type': 'x-token',
            'retpath': 'https://www.yandex.ru'
        }
        headers = {'Ya-Consumer-Authorization': f"OAuth {x_token}"}
        r = await self.session.post(
            'https://mobileproxy.passport.yandex.net/1/bundle/auth/x_token/',
            data=payload, headers=headers, proxy=self.proxy
        )
        resp = await r.json()
        if resp['status'] != 'ok':
            _LOGGER.error(f"Login with token error: {resp}")
            return False

        host = resp['passport_host']
        payload = {'track_id': resp['track_id']}
        r = await self.session.get(
            f"{host}/auth/session/", params=payload, proxy=self.proxy,
            allow_redirects=False
        )
        assert r.status == 302, await r.read()

        return True

    async def refresh_cookies(self) -> bool:
        """Checks if cookies ok and updates them if necessary."""
        # check cookies
        r = await self.session.get("https://yandex.ru/quasar?storage=1")
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
        """Get music token using x-token. Usual you should'n call this method.
        """
        _LOGGER.debug("Get music token")

        payload = {
            # Thanks to https://github.com/MarshalX/yandex-music-api/
            'client_secret': '53bc75238f0c4d08a118e51fe9203300',
            'client_id': '23cabbbdc6cd418abb4b39c32c41195d',
            'grant_type': 'x-token',
            'access_token': x_token
        }
        r = await self.session.post(
            'https://oauth.mobile.yandex.net/1/token', data=payload
        )
        resp = await r.json()
        assert 'access_token' in resp, resp
        return resp['access_token']

    async def get(self, url, **kwargs):
        if '/glagol/' in url:
            return await self._request_glagol(url, **kwargs)
        return await self._request('get', url, **kwargs)

    async def post(self, url, **kwargs):
        return await self._request('post', url, **kwargs)

    async def put(self, url, **kwargs):
        return await self._request('put', url, **kwargs)

    async def ws_connect(self, *args, **kwargs):
        return await self.session.ws_connect(*args, **kwargs)

    async def _request(self, method: str, url: str, retry: int = 2, **kwargs):
        # all except GET should contain CSRF token
        if method != 'get':
            if self.csrf_token is None:
                _LOGGER.debug(f"Обновление CSRF-токена, proxy: {self.proxy}")
                r = await self.session.get("https://yandex.ru/quasar",
                                           proxy=self.proxy)
                raw = await r.text()
                m = re.search('"csrfToken2":"(.+?)"', raw)
                assert m, raw
                self.csrf_token = m[1]

            kwargs['headers'] = {'x-csrf-token': self.csrf_token}

        r = await getattr(self.session, method)(url, **kwargs)
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
        else:
            _LOGGER.warning(f"{url} return {r.status} status")

        if retry:
            _LOGGER.debug(f"Retry {method} {url}")
            return await self._request(method, url, retry - 1, **kwargs)

        raise Exception(f"{url} return {r.status} status")

    async def _request_glagol(self, url: str, retry: int = 2, **kwargs):
        # update music token if needed
        if not self.music_token:
            assert self.x_token, "x-token required"
            self.music_token = await self.get_music_token(self.x_token)
            await self._handle_update()

        headers = {'Authorization': f"Oauth {self.music_token}"}
        r = await self.session.get(url, headers=headers, **kwargs)
        if r.status == 200:
            return r
        elif r.status == 403:
            # clear music token if problem
            self.music_token = None

        if retry:
            _LOGGER.debug(f"Retry {url}")
            return await self._request_glagol(url, retry - 1)

        raise Exception(f"{url} return {r.status} status")

    @property
    def cookie(self):
        # noinspection PyProtectedMember, PyUnresolvedReferences
        raw = pickle.dumps(self.session.cookie_jar._cookies,
                           pickle.HIGHEST_PROTOCOL)
        return base64.b64encode(raw).decode()

    async def _handle_update(self):
        for coro in self._update_listeners:
            await coro(x_token=self.x_token, music_token=self.music_token,
                       cookie=self.cookie)
