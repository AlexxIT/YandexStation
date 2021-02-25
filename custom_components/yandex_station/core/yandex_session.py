import base64
import json
import logging
import pickle
import re

from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)

HEADERS = {'User-Agent': 'com.yandex.mobile.auth.sdk/7.15.0.715001762'}

RE_CSRF = re.compile('"csrfToken2":"(.+?)"')


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
        return self.raw['status'] == 'ok'

    @property
    def error(self):
        return self.raw['errors'][0]

    @property
    def captcha_image_url(self):
        return self.raw.get('captcha_image_url')

    @property
    def external_url(self):
        return self.raw.get('external_url')

    @property
    def display_login(self):
        return self.raw['display_login']

    @property
    def x_token(self):
        return self.raw['x_token']


class YandexSession:
    """Class for login in yandex via username, token, capcha."""
    user = None
    x_token = None
    csrf_token = None
    music_token = None
    _payload: dict = None
    proxy: str = None

    def __init__(self, session: ClientSession, x_token: str = None,
                 music_token: str = None, cookie: str = None):
        """
        :param x_token: optional x-token from login_username or login_captcha
        :param music_token: optional token for glagol API
        :param cookie: optional base64 cookie from last session
        """
        self.session = session

        self.x_token = x_token
        self.music_token = music_token
        if cookie:
            raw = base64.b64decode(cookie)
            self.session.cookie_jar._cookie = pickle.loads(raw)

        self._update_listeners = []

    def add_update_listener(self, coro):
        """Listeners to handle automatic cookies update."""
        self._update_listeners.append(coro)

    async def login_username(self, username: str, password: str):
        """Login to Yandex with username and password"""
        _LOGGER.debug("Login in Yandex with username")

        payload = {
            'x_token_client_id': 'c0ebe342af7d48fbbbfcf2d2eedb8f9e',
            'x_token_client_secret': 'ad0a908f0aa341a182a37ecd75bc319e',
            'client_id': 'f8cab64f154b4c8e96f92dac8becfcaa',
            'client_secret': '5dd2389483934f02bd51eaa749add5b2',
            'display_language': 'ru',
            'force_register': 'false',
            'is_phone_number': 'false',
            'login': username,
        }
        r = await self.session.post(
            'https://mobileproxy.passport.yandex.net/2/bundle/mobile/start/',
            data=payload, headers=HEADERS)
        resp = await r.json()
        track_id = resp.get('track_id')
        assert track_id, resp

        self._payload = {
            'password_source': 'Login',
            'password': password,
            'track_id': track_id
        }
        r = await self.session.post(
            'https://mobileproxy.passport.yandex.net/1/bundle/mobile/auth/'
            'password/', data=self._payload, headers=HEADERS)
        resp = await r.json()

        if ('errors' in resp and
                resp['errors'][0] == 'action.required_external_or_native'):
            resp['external_url'] = (
                f"https://passport.yandex.com/auth?track_id={track_id}"
            )

        return LoginResponse(resp)

    async def login_captcha(self, captcha_answer: str):
        """Login with answer to captcha from login_username."""
        _LOGGER.debug("Login in Yandex with captcha")

        self._payload['password_source'] = 'captcha'
        self._payload['captcha_answer'] = captcha_answer

        r = await self.session.post(
            'https://mobileproxy.passport.yandex.net/1/bundle/mobile/auth/'
            'password/', data=self._payload, headers=HEADERS)
        resp = await r.json()
        return LoginResponse(resp)

    async def login_cookies(self, cookies: str):
        """Support format Google Chrome, extension: Copy Cookies
        https://chrome.google.com/webstore/detail/copy-cookies/jcbpglbplpblnagieibnemmkiamekcdg
        """
        raw = json.loads(cookies)
        cookies = {p['name']: p['value'] for p in raw}

        payload = {
            'grant_type': 'sessionid',
            'client_id': 'c0ebe342af7d48fbbbfcf2d2eedb8f9e',
            'client_secret': 'ad0a908f0aa341a182a37ecd75bc319e',
            'host': 'passport.yandex.com',
        }
        r = await self.session.post(
            'https://mobileproxy.passport.yandex.net/1/token',
            data=payload, headers=HEADERS, cookies=cookies
        )
        resp = await r.json()
        x_token = resp['access_token']

        return await self.validate_token(x_token)

    async def validate_token(self, x_token):
        """Return user info using token."""
        headers = {'Authorization': f"OAuth {x_token}"}
        r = await self.session.get(
            'https://mobileproxy.passport.yandex.net/1/bundle/account/'
            'short_info/?avatar_size=islands-300', headers=headers
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
            'retpath': 'https://www.yandex.ru/androids.txt'
        }
        headers = {'Ya-Consumer-Authorization': f"OAuth {x_token}"}
        r = await self.session.post(
            'https://mobileproxy.passport.yandex.net/1/bundle/auth/x_token/',
            data=payload, headers=headers)
        resp = await r.json()
        if resp['status'] != 'ok':
            _LOGGER.error(f"Login with token error: {resp}")
            return False

        host = resp['passport_host']
        payload = {'track_id': resp['track_id']}
        r = await self.session.get(f"{host}/auth/session/", params=payload,
                                   proxy=self.proxy)
        assert r.status == 404, await r.read()

        return True

    async def refresh_cookies(self):
        # check cookies
        r = await self.session.get(
            'https://quasar.yandex.ru/get_account_config')
        resp = await r.json()
        if resp['status'] == 'ok':
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
        r = await self.session.post('https://oauth.mobile.yandex.net/1/token',
                                    data=payload)
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
                r = await self.session.get('https://yandex.ru/quasar/iot',
                                           proxy=self.proxy)
                raw = await r.text()
                m = RE_CSRF.search(raw)
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
