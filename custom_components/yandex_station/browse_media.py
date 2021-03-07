"""Support for media browsing."""
__all__ = [
    "YandexMusicBrowser",
    "register_type_browse_processor",
    "adapt_media_id_to_user_id",
    "adapt_media_browse_processor",
    "adapt_directory_to_browse_processor",
    "MAP_MEDIA_OBJECT_TO_BROWSE",
    "MAP_MATCHER_TO_MEDIA_TYPE",
    "MAP_MEDIA_TYPE_TO_BROWSE",
    "MissingMediaInformation",
    "UnknownMediaType",
    "TimeoutDataFetching"
]

import functools
import logging
import re
from abc import ABC
from copy import deepcopy
from json import dumps
from time import time
from typing import Union, Optional, Iterable, List, Dict, Tuple, Mapping, Any, Callable, Type, TypeVar, Hashable

from homeassistant.components.media_player import BrowseError, BrowseMedia
from homeassistant.components.media_player.const import MEDIA_CLASS_PLAYLIST, MEDIA_CLASS_ARTIST, MEDIA_CLASS_ALBUM, \
    MEDIA_CLASS_TRACK, MEDIA_CLASS_GENRE, MEDIA_TYPE_PLAYLIST, MEDIA_TYPE_ALBUM, MEDIA_TYPE_ARTIST, \
    MEDIA_TYPE_TRACK, MEDIA_CLASS_DIRECTORY
from homeassistant.const import CONF_TIMEOUT
from yaml import load, YAMLError, BaseLoader
from yandex_music import Client, TrackShort, Track, Playlist, Artist, Album, MixLink, PlaylistId, \
    TagResult, Tag, Genre, YandexMusicObject

from custom_components.yandex_station.const import CONF_LANGUAGE, \
    CONF_CACHE_TTL, CONF_MENU_OPTIONS, CONF_THUMBNAIL_RESOLUTION, CONF_WIDTH, CONF_HEIGHT, \
    EXPLICIT_UNICODE_ICON_STANDARD, MEDIA_TYPE_MIX_TAG, MEDIA_TYPE_GENRE, CONF_SHOW_HIDDEN, MEDIA_TYPE_RADIO, \
    CONF_LYRICS, CONF_ITEMS, ROOT_MEDIA_CONTENT_TYPE, CONF_TITLE, CONF_IMAGE
from custom_components.yandex_station.core.utils import recursive_dict_update

_LOGGER = logging.getLogger(__name__)


MediaObjectType = Union[str, YandexMusicObject, tuple, Any]
MediaObjectReturnType = Optional[MediaObjectType]
MediaObjectsReturnType = Optional[List[MediaObjectType]]

PreferredResolutionType = Optional[Union[int, Tuple[int, int], str]]

AnyPatternType = Union[re.Pattern, str]
FetchChildrenType = Union[bool, int]

CustomResolverCallback = Callable[[re.Match], str]

MediaContentIDType = str

_MediaObjectType = TypeVar('_MediaObjectType', bound=MediaObjectType)
BrowseGeneratorReturnType = Optional[BrowseMedia]
BrowseGeneratorType = Callable[
    ['YandexMusicBrowser', MediaObjectReturnType, FetchChildrenType],
    BrowseGeneratorReturnType
]

DirectoryChildrenType = Callable[['YandexMusicBrowser', MediaContentIDType], MediaObjectsReturnType]

MediaProcessorType = Callable[['YandexMusicBrowser', str], MediaObjectReturnType]

MAP_MEDIA_OBJECT_TO_BROWSE: Dict[Type[_MediaObjectType], BrowseGeneratorType] = {}
MAP_MEDIA_TYPE_TO_BROWSE: Dict[str, BrowseGeneratorType] = {}
MAP_MATCHER_TO_MEDIA_TYPE: Dict[re.Pattern, Tuple[CustomResolverCallback, BrowseGeneratorType]] = {}


DEFAULT_TITLE_LANGUAGE = "en"
DEFAULT_REQUEST_TIMEOUT = 15

THUMBNAIL_EMPTY_IMAGE = '/non/exiswtent/thumbnail/generate/404'

ITEM_RESPONSE_CACHE = {}


class MissingMediaInformation(BrowseError):
    """Missing media required information."""


class UnknownMediaType(BrowseError):
    """Unknown media type."""


class TimeoutDataFetching(BrowseError):
    """Timed out while fetching data"""


class InvalidUserMediaID(BrowseError):
    """Raised when media_content_id contains invalid user_id"""


_USER_ID_CACHE = {}
_USER_LOGIN_CACHE = {}


def extract_user_data(media_content_id: Union[MediaContentIDType, Client]) -> Optional[Dict[str, Any]]:
    """Extract user ID from media_content_id"""
    if isinstance(media_content_id, Client):
        acc = media_content_id.me.account

        data = {"uid": acc.uid, "login": acc.login,
                "name": acc.display_name}
        _USER_ID_CACHE[acc.uid] = data
        _USER_LOGIN_CACHE[acc.login] = data

        return data

    if media_content_id.startswith('#'):
        uid = media_content_id[1:]
        return _USER_ID_CACHE.get(uid, {"uid": uid})

    if media_content_id in _USER_LOGIN_CACHE:
        return _USER_LOGIN_CACHE[media_content_id]

    from requests import get
    from json import loads, JSONDecodeError
    r = get(url=f'https://music.yandex.ru/users/{media_content_id}/playlists')

    # Please, do not block this <3
    for m in re.compile(r'"owner"\s*:\s*(\{[^\}]+\})').finditer(r.text):
        try:
            data = loads(m.group(1))
        except (JSONDecodeError, ValueError):
            continue

        uid = data.get('uid')
        login = data.get('login')

        if 'avatarHash' in data:
            data['image'] = 'https://avatars.mds.yandex.net/get-yapic/' + data.pop('avatarHash') + '/islands-300'

        if uid not in _USER_ID_CACHE:
            _USER_ID_CACHE[uid] = data
        if login not in _USER_LOGIN_CACHE:
            _USER_LOGIN_CACHE[login] = data

    return _USER_LOGIN_CACHE.get(media_content_id)


def sanitize_thumbnail_uri(
        thumbnail: str,
        preferred_resolution: PreferredResolutionType = None
) -> str:
    """
    Helper function to apply common replacement operations on thumbnail URIs.
    :param thumbnail: Thumbnail URI
    :param preferred_resolution: (optional) Preferred thumbnail resolution (if applicable)
    :return: None
    """
    if thumbnail == THUMBNAIL_EMPTY_IMAGE:
        return thumbnail

    if '%%' in thumbnail:
        if preferred_resolution is None:
            preferred_resolution = (200, 200)
        elif isinstance(preferred_resolution, int):
            preferred_resolution = (preferred_resolution, preferred_resolution)

        if isinstance(preferred_resolution, tuple):
            preferred_resolution = f'{preferred_resolution[0]}x{preferred_resolution[1]}'

        thumbnail = thumbnail.replace('%%', preferred_resolution)

    if thumbnail.startswith('/') and not thumbnail.startswith('//'):
        thumbnail = 'https://music.yandex.ru' + thumbnail

    elif not thumbnail.startswith(('http://', 'https://')):
        thumbnail = 'https://' + thumbnail

    return thumbnail


def sanitize_browse_thumbnail(
        browse_object: BrowseMedia,
        default_thumbnail: Optional[str] = None,
        preferred_resolution: PreferredResolutionType = None
) -> None:
    """
    Helper function to apply sanitation to browse objects.
    :param browse_object: Browse object
    :param default_thumbnail: (optional) Default thumbnail to apply on thumbnail absence
    :param preferred_resolution: (optional) Preferred thumbnail resolution (if applicable)
    :return: None
    """
    if browse_object.thumbnail:
        browse_object.thumbnail = sanitize_thumbnail_uri(browse_object.thumbnail, preferred_resolution)
    elif default_thumbnail:
        browse_object.thumbnail = sanitize_thumbnail_uri(default_thumbnail, preferred_resolution)


def find_genre_recursive(genre_id: str, genres_list: List[Genre]) -> Optional[Genre]:
    """Find genre by ID"""
    for genre in genres_list:
        if genre.id == genre_id:
            return genre
        if genre.sub_genres:
            sub_genre = find_genre_recursive(genre_id, genre.sub_genres)
            if sub_genre:
                return sub_genre


def extract_name_from_function(func: Callable):
    name = str(func.__name__)

    if name.endswith('_processor'):
        return name[:-10]
    return name


def tuplify(value):
    if isinstance(value, list):
        return tuple(tuplify(x) for x in value)
    else:
        return value


RE_MEDIA_LINK = re.compile(r'([^\(\)]+)(\([^)(]+\)|)')


def sanitize_media_link(value: Union[str, Tuple[str, Optional[str]]], validate: bool = True):
    if isinstance(value, tuple):
        media_content_type, media_content_id = value
    else:
        match = RE_MEDIA_LINK.fullmatch(value)
        if match:
            media_content_type = match.group(1)
            media_content_id = match.group(2)[1:-1] if match.group(2) else None
        else:
            raise ValueError(f'element `{value}` does not comply with value formatting')

        if media_content_type == ROOT_MEDIA_CONTENT_TYPE:
            raise ValueError(f'values with media type `{value}` not allowed')

        if validate:
            type_browse_generator = MAP_MEDIA_TYPE_TO_BROWSE.get(media_content_type)
            if type_browse_generator is None:
                raise ValueError(f'element `{value}` does not exist as a type')

            media_content_id_validator: Callable[[MediaContentIDType], Optional[bool]] = \
                getattr(type_browse_generator, MEDIA_CONTENT_ID_VALIDATOR_ATTRIBUTE)

            if media_content_id_validator(media_content_id) is False:
                raise ValueError(f'type argument `{media_content_id}` did not pass validation')

    return media_content_type, media_content_id


_ListItemsHierarchyType = Iterable[Union[Tuple[str, str], str, Iterable['_ListHierarchyType']]]
_ListHierarchyType = Mapping[str, Optional[Union[str, _ListItemsHierarchyType]]]
_HierarchyType = List[Dict[str, Optional[Union[str, Tuple[str, Optional[str]]]]]]


class BrowseTree:
    def __init__(self, hierarchy: _HierarchyType):
        if isinstance(hierarchy, BrowseTree):
            hierarchy = deepcopy(hierarchy.hierarchy)

        self.hierarchy = hierarchy

    def __str__(self):
        return str(self.hierarchy)

    def __repr__(self):
        return f'<{self.__class__.__name__}:{self}>'

    def __eq__(self, other: 'BrowseTree'):
        return self.hierarchy == other.hierarchy

    def __getitem__(self, item: Union[int, str]):
        return self.hierarchy[int(item)]

    @classmethod
    def _str_to_map(cls, serialized_str: str, validate: bool = True) -> _ListHierarchyType:
        try:
            return load(serialized_str, Loader=BaseLoader)
        except YAMLError:
            raise ValueError(str(YAMLError)) from None

    @classmethod
    def _map_to_hierarchy(cls, base_array: _ListHierarchyType, validate: bool = True, collection: Optional[_HierarchyType] = None) -> _HierarchyType:
        if collection is None:
            collection = []

        if 'items' not in base_array:
            raise ValueError('`items` key not present in dictionary')
        else:
            existing_items = base_array['items']

        new_items = []
        collection.append({
            'title': base_array.get('title'),
            'image': base_array.get('image'),
            'class': base_array.get('class'),
            'items': new_items
        })

        for value in existing_items:
            if isinstance(value, Mapping):
                new_items.append((ROOT_MEDIA_CONTENT_TYPE, len(collection)))

                cls._map_to_hierarchy(
                    value,
                    validate=validate,
                    collection=collection
                )

            else:
                if isinstance(value, str):
                    match = RE_MEDIA_LINK.fullmatch(value)
                    if match:
                        media_content_type = match.group(1)
                        media_content_id = match.group(2)[1:-1] if match.group(2) else None
                    else:
                        raise ValueError(f'invalid media link definition: {value}')

                elif isinstance(value, tuple):
                    media_content_type, media_content_id = value

                else:
                    raise TypeError(f'invalid type encountered: {type(value)}')

                if media_content_type == ROOT_MEDIA_CONTENT_TYPE:
                    raise ValueError(f'media links of type `{ROOT_MEDIA_CONTENT_TYPE}` are not allowed')

                if validate:
                    processor = MAP_MEDIA_TYPE_TO_BROWSE.get(media_content_type)
                    if processor is None:
                        raise ValueError(f'media content type `{media_content_type}` not found')

                    validation = getattr(processor, '__media_content_id_validator')(media_content_id)
                    if validation is False:
                        raise ValueError(f'media content ID `{media_content_id}` is invalid')

                new_items.append((media_content_type, media_content_id))

        return collection

    @classmethod
    def from_str(cls, source: str, validate: bool = True):
        return cls(cls._map_to_hierarchy(cls._str_to_map(source, validate=validate), validate=validate))

    @classmethod
    def from_map(cls, value: _ListHierarchyType, validate: bool = True):
        return cls(cls._map_to_hierarchy(value, validate=validate))

    @classmethod
    def _hierarchy_to_map(cls, hierarchy: _HierarchyType, links_as_tuples: bool = False) -> _ListHierarchyType:
        new_array = deepcopy(hierarchy)

        for i, hierarchy_settings in enumerate(new_array):
            for x in ['title', 'image', 'class']:
                if hierarchy_settings[x] is None:
                    del hierarchy_settings[x]

        for i, hierarchy_settings in enumerate(new_array):
            items = hierarchy_settings.get('items')
            if items is None:
                raise ValueError('`items` key is missing from hierarchy')

            for j, value in enumerate(items):
                if isinstance(value, tuple):
                    media_content_type, media_content_id = value
                    if media_content_type == ROOT_MEDIA_CONTENT_TYPE:
                        items[j] = new_array[int(media_content_id)]
                    elif not links_as_tuples:
                        if media_content_id is None:
                            items[j] = media_content_type
                        else:
                            items[j] = f'{media_content_type}({media_content_id})'

        return new_array[0]

    def to_map(self, links_as_tuples: bool = False):
        return self._hierarchy_to_map(self.hierarchy, links_as_tuples=links_as_tuples)

    @classmethod
    def _map_to_str(cls, base_array: _ListHierarchyType) -> str:
        return dumps(base_array, separators=(',', ':'))

    def to_str(self, as_json: bool = False):
        return self._map_to_str(self._hierarchy_to_map(self.hierarchy))


class _TranslationsDict(dict):
    def __missing__(self, key):
        return '{' + str(key) + '}'


class _YandexMediaBrowserBase(ABC):
    _USER_ID_CACHE = {}

    DEFAULT_CACHE_TTL = 600
    DEFAULT_TIMEOUT = 15
    DEFAULT_LANGUAGE = 'en'
    DEFAULT_MENU_OPTIONS: BrowseTree = None  # set at the end of the file when all processors are ready
    DEFAULT_THUMBNAIL_RESOLUTION = (200, 200)
    DEFAULT_SHOW_HIDDEN = False
    DEFAULT_LYRICS = False

    def __init__(
            self,
            authentication: Union[Tuple[str, str], str, Client],
            browser_config: Optional[Mapping[str, Any]] = None,
    ):
        self._cache_ttl = None
        self._timeout = None
        self._menu_options = None
        self._thumbnail_resolution = None
        self._show_hidden = None
        self._lyrics = None
        self._client = None
        self._language_strings = None
        self._response_cache = {}
        self._oldest_cache_entry = time()

        if isinstance(authentication, Client):
            client = authentication
        elif isinstance(authentication, str):
            client = Client.from_token(authentication)
        elif isinstance(authentication, tuple):
            client = Client.from_credentials(*authentication)
        else:
            raise TypeError('invalid authentication method provided')

        self._original_client = client

        extract_user_data(client)

        self.browser_config = browser_config

    # Client management properties
    @property
    def client(self) -> Client:
        return (self._original_client
                if self._client is None
                else self._client)

    @client.setter
    def client(self, value: Optional[Client]):
        self._client = value
        if value is not None:
            extract_user_data(value)

        self.clear_cache()

    # Browser configuration properties
    @property
    def lyrics(self) -> bool:
        return (self.DEFAULT_LYRICS
                if self._lyrics is None
                else self._lyrics)

    @lyrics.setter
    def lyrics(self, value: Optional[bool]):
        self._lyrics = value
        self.clear_cache()

    @property
    def show_hidden(self) -> bool:
        return (self.DEFAULT_SHOW_HIDDEN
                if self._show_hidden is None
                else self._show_hidden)

    @show_hidden.setter
    def show_hidden(self, value: Optional[bool]):
        self._show_hidden = value
        self.clear_cache()

    @property
    def cache_ttl(self) -> Union[int, float]:
        return (self.DEFAULT_CACHE_TTL
                if self._cache_ttl is None
                else self._cache_ttl)

    @cache_ttl.setter
    def cache_ttl(self, value: Optional[Union[int, float]]):
        self._cache_ttl = value

    @property
    def menu_options(self) -> Tuple[str]:
        return (self.DEFAULT_MENU_OPTIONS
                if self._menu_options is None
                else self._menu_options)

    @menu_options.setter
    def menu_options(self, value: Union[_ListHierarchyType, BrowseTree]):
        if isinstance(value, Mapping):
            value = BrowseTree.from_map(value)
        elif isinstance(value, str):
            value = BrowseTree.from_str(value)
        elif not isinstance(value, BrowseTree):
            raise TypeError('invalid value type (%s)' % (type(value),))
        self._menu_options = value

    @property
    def thumbnail_resolution(self) -> Tuple[int, int]:
        return (self.DEFAULT_THUMBNAIL_RESOLUTION
                if self._thumbnail_resolution is None
                else self._thumbnail_resolution)

    @thumbnail_resolution.setter
    def thumbnail_resolution(self, value: Optional[Tuple[int, int]]):
        self._thumbnail_resolution = value
        self.clear_cache()

    @property
    def language(self) -> str:
        return self.client.request.headers['Accept-Language']

    @language.setter
    def language(self, language: Optional[str]) -> None:
        language = language or self.DEFAULT_LANGUAGE
        self.client.request.set_language(language)

        from os.path import dirname, isfile, join, realpath
        from json import load

        root_translations_key = 'media_browser'
        translations_dir = join(dirname(realpath(__file__)), 'translations')

        default_translation_file = join(translations_dir, self.DEFAULT_LANGUAGE + '.json')
        with open(default_translation_file, 'r') as f:
            self._language_strings = load(f).get(root_translations_key, {})

        if language != self.DEFAULT_LANGUAGE:
            translation_file = join(translations_dir, language + '.json')
            if isfile(translation_file):
                with open(translation_file, 'r') as f:
                    recursive_dict_update(
                        self._language_strings,
                        load(f).get(root_translations_key, {})
                    )

        self.clear_cache()

    @property
    def browser_config(self):
        browser_config = {
            CONF_LANGUAGE: self.language,
        }

        if self._cache_ttl is not None:
            browser_config[CONF_CACHE_TTL] = self._cache_ttl

        if self._timeout is not None:
            browser_config[CONF_TIMEOUT] = self._cache_ttl

        if self._menu_options is not None:
            browser_config[CONF_MENU_OPTIONS] = self._menu_options

        if self._thumbnail_resolution is not None:
            browser_config[CONF_THUMBNAIL_RESOLUTION] = {
                CONF_WIDTH: self._thumbnail_resolution[0],
                CONF_HEIGHT: self._thumbnail_resolution[1]
            }

        if self._show_hidden is not None:
            browser_config[CONF_SHOW_HIDDEN] = self._show_hidden

        if self._lyrics is not None:
            browser_config[CONF_LYRICS] = self._lyrics

        return browser_config

    @browser_config.setter
    def browser_config(self, browser_config: Optional[Mapping[str, Any]]):
        browser_config = browser_config or {}

        self.cache_ttl = browser_config.get(CONF_CACHE_TTL)
        self.timeout = browser_config.get(CONF_TIMEOUT)
        self.menu_options = browser_config.get(CONF_MENU_OPTIONS)

        self._show_hidden = browser_config.get(CONF_SHOW_HIDDEN)
        self._lyrics = browser_config.get(CONF_LYRICS)

        thumbnail_resolution = browser_config.get(CONF_THUMBNAIL_RESOLUTION)
        if thumbnail_resolution is not None:
            self._thumbnail_resolution = (
                thumbnail_resolution[CONF_WIDTH],
                thumbnail_resolution[CONF_HEIGHT]
            )

        # This will clear response cache
        self.language = browser_config.get(CONF_LANGUAGE)

    # Cache management
    @property
    def response_cache(self) -> dict:
        return self._response_cache

    def clear_cache(self):
        self._response_cache.clear()

    # Data-driven properties
    @property
    def user_id(self) -> str:
        return str(self.client.me.account.uid)

    def get_translation(self, media_type: str, translation: str, **kwargs) -> Optional[str]:
        """Get translation for media_type"""

        return self._language_strings \
            .get(media_type, {}) \
            .get(translation, f'%{media_type}.{translation}%') \
            .format_map(_TranslationsDict(kwargs))

    def generate_browse_from_media(
            self,
            media_object: _MediaObjectType,
            fetch_children: FetchChildrenType = True,
            cache_garbage_collection: bool = False
    ) -> BrowseGeneratorReturnType:
        processor = MAP_MEDIA_OBJECT_TO_BROWSE.get(type(media_object))

        if processor is None:
            for processor_cls, processor_fn in MAP_MEDIA_OBJECT_TO_BROWSE.items():
                if isinstance(media_object, processor_cls):
                    processor = processor_fn
                    break

        if processor is None:
            return None

        browse_object = processor(self, media_object, fetch_children)

        if browse_object is not None:
            sanitize_browse_thumbnail(browse_object, preferred_resolution=self.thumbnail_resolution)

        if cache_garbage_collection:
            _LOGGER.debug('Running garbage collection')
            now = int(time())
            cache_ttl = self.cache_ttl

            if now - self._oldest_cache_entry >= cache_ttl:
                _LOGGER.debug('Oldest cache entry is: %s', self._oldest_cache_entry)

                oldest_cache = time()
                remove_keys = []
                for cache_key, (created_at, _) in self._response_cache.items():
                    if now - created_at >= cache_ttl:
                        remove_keys.append(cache_key)
                    elif created_at < oldest_cache:
                        oldest_cache = created_at

                for cache_key in remove_keys:
                    del self._response_cache[cache_key]

                _LOGGER.debug('Removed %d items from cache', len(remove_keys))

                self._oldest_cache_entry = oldest_cache
            else:
                _LOGGER.debug('Garbage collection not required (will perform next in %d seconds)',
                              self._oldest_cache_entry + self.cache_ttl - now)

        return browse_object

    def generate_browse_list_from_media_list(
            self,
            media_objects: Iterable[_MediaObjectType],
            fetch_children: FetchChildrenType = False,
    ) -> List[BrowseGeneratorReturnType]:
        if fetch_children:
            fetch_children = int(fetch_children) - 1

        browse_objects = []
        for media_object in media_objects:
            browse_object = self.generate_browse_from_media(
                media_object,
                fetch_children=fetch_children
            )
            if browse_object is not None:
                browse_objects.append(browse_object)

        return browse_objects


class YandexMusicBrowser(_YandexMediaBrowserBase):
    def get_playlists_from_ids(
            self,
            playlist_ids: List[Union[Dict[str, Union[int, str]], PlaylistId]],
    ) -> List[Playlist]:
        """
        Wrapper around lists retriever for different playlist ID types.
        :param self:
        :param playlist_ids: List of playlist IDs
        :return: List[Playlist]
        """
        # noinspection PyUnresolvedReferences
        playlist_ids = [
            playlist if isinstance(playlist, str) else f'{playlist["uid"]}:{playlist["kind"]}'
            for playlist in playlist_ids
        ]
        return self.client.playlists_list(playlist_ids=playlist_ids, timeout=self.timeout)


MEDIA_CONTENT_ID_VALIDATOR_ATTRIBUTE = '__media_content_id_validator'


def register_type_browse_processor(
        media_content_type: Optional[str] = None,
        media_id_pattern: Optional[Union[AnyPatternType, bool]] = None,
        force_media_content_type: bool = True,
        default_media_id: Optional[str] = None,
        cache_on_demand: bool = True
) -> Callable[[BrowseGeneratorType], BrowseGeneratorType]:
    """
    Decorator that registers function as a type resolver.
    :param media_content_type: Directory alias (derived from function name if absent)
    :param media_id_pattern: Pattern to validate provided media ID
                             (`True` for forcing any non-empty ID,
                              `False` for requiring empty media ID,
                              `None` for not checking media ID)
    :param force_media_content_type: Force provided media content type onto root objects
    :param default_media_id: Default media ID when empty media ID is encountered
    :param cache_on_demand: Cache browse object when demanded (default = True)
    :return: Decorator
    """
    if isinstance(media_id_pattern, str):
        media_id_pattern = re.compile(media_id_pattern)

    if isinstance(media_id_pattern, re.Pattern):
        def _media_content_id_validator(media_content_id: Optional[str] = None) -> bool:
            return bool(media_content_id and media_id_pattern.fullmatch(media_content_id))

    elif isinstance(media_id_pattern, bool):
        def _media_content_id_validator(media_content_id: Optional[str] = None) -> bool:
            return media_id_pattern ^ bool(media_content_id)

    else:
        def _media_content_id_validator(media_content_id: Optional[str] = None) -> bool:
            return True

    def _decorate(func: BrowseGeneratorType) -> BrowseGeneratorType:
        setattr(func, MEDIA_CONTENT_ID_VALIDATOR_ATTRIBUTE, _media_content_id_validator)

        @functools.wraps(func)
        def wrapped_function(
                browser: YandexMusicBrowser,
                media_content_id: MediaContentIDType = None,
                fetch_children: FetchChildrenType = True,
        ) -> BrowseGeneratorReturnType:
            if media_content_id is None:
                media_content_id = default_media_id

            cache_key = None
            if cache_on_demand:
                if isinstance(media_content_id, Hashable):
                    cache_key = (_media_content_type, media_content_id)
                    if cache_key in browser.response_cache:
                        return browser.response_cache[cache_key][1]
                else:
                    _LOGGER.debug('%s not of hashable type (%s)', media_content_id, type(media_content_type))

            # this could be without hasattr(...) and getattr(...),
            # but what if something removes the attribute at runtime...
            if not getattr(func, MEDIA_CONTENT_ID_VALIDATOR_ATTRIBUTE)(media_content_id):
                return None

            browse_object = func(
                browser,
                media_content_id,
                fetch_children
            )

            if force_media_content_type and isinstance(browse_object, BrowseMedia):
                browse_object.media_content_type = _media_content_type

            if cache_key is not None:
                browser.response_cache[cache_key] = (time(), browse_object)

            return browse_object

        wrapped_function.__name__ = func.__name__

        if isinstance(media_content_type, str):
            _media_content_type = media_content_type
        elif func.__name__ is None:
            raise ValueError('cannot extrapolate function name')
        else:
            _media_content_type = extract_name_from_function(func)

        if '(' in _media_content_type or ')' in _media_content_type:
            raise ValueError('media_content_type contains invalid characters')

        MAP_MEDIA_TYPE_TO_BROWSE[_media_content_type] = wrapped_function

        return wrapped_function

    return _decorate


def adapt_media_id_to_user_id() -> Callable[[BrowseGeneratorType], BrowseGeneratorType]:
    def _decorate(func: BrowseGeneratorType) -> BrowseGeneratorType:
        @functools.wraps(func)
        def wrapped_function(
                browser: YandexMusicBrowser,
                media_content_id: MediaContentIDType = None,
                fetch_children: FetchChildrenType = True
        ) -> BrowseGeneratorReturnType:
            if media_content_id is None:
                user_id = browser.user_id
            else:
                user_data = extract_user_data(media_content_id)
                if user_data is None or 'uid' not in user_data:
                    _LOGGER.debug('Could not extract user ID from: %s', media_content_id)
                    return None

                user_id = user_data['uid']

            return func(browser, f'#{user_id}', fetch_children)

        wrapped_function.__name__ = func.__name__

        return wrapped_function

    return _decorate


def adapt_directory_to_browse_processor(
        children_media_class: Optional[str] = None,
        thumbnail: Optional[str] = None,
        can_play: bool = False,
        can_expand: bool = True,
        translation_key: Optional[str] = None,
) -> Callable[[DirectoryChildrenType], BrowseGeneratorType]:
    """
    Decorator that creates generators for directories.
    :param children_media_class: (optional) Media class of directory's children
    :param thumbnail: (optional) Default directory thumbnail URI
    :param can_play: (optional) Whether directory can be used for playback (default = true)
    :param can_expand: (optional) Whether directory can be expanded (default = true)
    :param translation_key: Translation key to fetch main translations from
    :return: Decorator
    """

    def _decorate(func: DirectoryChildrenType) -> BrowseGeneratorType:
        """
        Decorate directory children fetching function, and add it to the generators registry.
        :param func: Function that fetches directory's children
        :return: Wrapped function
        """
        _translation_key = extract_name_from_function(func) if translation_key is None else translation_key

        @functools.wraps(func)
        def wrapped_function(
                browser: YandexMusicBrowser,
                media_content_id: Optional[MediaContentIDType] = None,
                fetch_children: FetchChildrenType = True
        ) -> BrowseGeneratorReturnType:
            if media_content_id is None:
                media_content_id = MEDIA_CLASS_DIRECTORY

            if fetch_children:
                fetch_children = int(fetch_children) - 1
                child_media_objects = func(browser, media_content_id)

                if child_media_objects:
                    children = browser.generate_browse_list_from_media_list(
                        child_media_objects,
                        fetch_children=fetch_children
                    )
                else:
                    children = []
            else:
                children = None

            title = browser.get_translation(_translation_key, 'title')
            
            return BrowseMedia(
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_id=media_content_id,
                media_content_type='',
                title=title,
                can_play=can_play,
                can_expand=can_expand,
                children=children,
                children_media_class=children_media_class,
                thumbnail=thumbnail
            )

        wrapped_function.__name__ = func.__name__

        return wrapped_function
    
    return _decorate


def adapt_type_to_browse_processor() -> Callable[[MediaProcessorType], BrowseGeneratorType]:
    """
    Create generator for media objects from provided ID's
    :return: Decorator
    """
    def _decorate(func: MediaProcessorType):
        """
        Decorate
        :param func: 
        :return: 
        """
        @functools.wraps(func)
        def wrapped_function(
                browser: YandexMusicBrowser,
                media_content_id: MediaContentIDType = None,
                fetch_children: FetchChildrenType = True,
        ) -> BrowseGeneratorReturnType:
            media_object = func(browser, media_content_id)
            
            if media_object is not None:
                return browser.generate_browse_from_media(
                    media_object,
                    fetch_children=fetch_children
                )

        wrapped_function.__name__ = func.__name__

        return wrapped_function

    return _decorate


def adapt_media_browse_processor(
        media_object_cls: Type[_MediaObjectType],
        thumbnail: Optional[str] = None,
) -> Callable[[BrowseGeneratorType], BrowseGeneratorType]:
    """
    Register media to browse converter.
    :param media_object_cls: (required) Media object class
    :param thumbnail:
    :return:
    """

    def _decorate(func: BrowseGeneratorType) -> BrowseGeneratorType:
        @functools.wraps(func)
        def wrapped_function(
                browser: YandexMusicBrowser,
                media_object: _MediaObjectType,
                fetch_children: FetchChildrenType = True
        ) -> BrowseGeneratorReturnType:
            # @TODO: post-processing
            browse_object = func(browser, media_object, fetch_children)

            if browse_object:
                sanitize_browse_thumbnail(
                    browse_object,
                    default_thumbnail=thumbnail,
                    preferred_resolution=browser.thumbnail_resolution
                )

            return browse_object

        wrapped_function.__name__ = func.__name__

        MAP_MEDIA_OBJECT_TO_BROWSE[media_object_cls] = wrapped_function

        return wrapped_function

    return _decorate


@register_type_browse_processor(media_content_type='user')
@adapt_media_id_to_user_id()
def user_processor(
        browser: 'YandexMusicBrowser',
        media_content_id: MediaContentIDType, fetch_children: FetchChildrenType
) -> BrowseGeneratorReturnType:
    data = extract_user_data(media_content_id)

    if data is None or 'uid' not in data:
        return None

    title = data.get('name')
    if not title:
        title = browser.get_translation('user', 'title', user_id=data['uid'])

    if fetch_children:
        children = [
            (x, media_content_id)
            for x in ('user_playlists', 'user_liked_playlists',
                      'user_liked_albums', 'user_liked_tracks',
                      'user_liked_artists')
        ]

        fetch_children = int(fetch_children) - 1
        children = browser.generate_browse_list_from_media_list(
            children,
            fetch_children=fetch_children
        )
    else:
        children = None

    return BrowseMedia(
        title=title,
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_type='user',
        media_content_id=media_content_id,
        children=children,
        can_play=False,
        can_expand=True,
        thumbnail=data.get('image')
    )


@register_type_browse_processor(media_content_type=ROOT_MEDIA_CONTENT_TYPE, default_media_id='0')
def library_processor(browser: 'YandexMusicBrowser', media_id: Union[int, str], fetch_children: FetchChildrenType) -> BrowseGeneratorReturnType:
    level_index = int(media_id)
    menu_options = browser.menu_options

    try:
        level_definition = menu_options[level_index]
    except (IndexError, ValueError, TypeError):
        _LOGGER.debug('Invalid folder ID requested: %s (type: %s)', media_id, type(media_id))
        return None

    if fetch_children:
        try:
            options = level_definition[CONF_ITEMS]
        except (KeyError, ValueError, TypeError):
            return None

        fetch_children = int(fetch_children) - 1
        children = browser.generate_browse_list_from_media_list(
            options,
            fetch_children=fetch_children
        )

    else:
        children = None

    if level_definition[CONF_TITLE]:
        title = level_definition[CONF_TITLE]
    elif level_index == 0:
        title = browser.get_translation(ROOT_MEDIA_CONTENT_TYPE, 'title')
    else:
        title = browser.get_translation(ROOT_MEDIA_CONTENT_TYPE, 'folder')

    return BrowseMedia(
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_type=ROOT_MEDIA_CONTENT_TYPE,
        media_content_id=str(media_id),
        title=title,
        can_play=False,
        can_expand=True,
        children=children,
        children_media_class=MEDIA_CLASS_DIRECTORY,
        thumbnail=level_definition[CONF_IMAGE]
    )


@register_type_browse_processor(MEDIA_TYPE_RADIO)
def generate_radio_object(
        browser: 'YandexMusicBrowser',
        media_content_id: Union[str, YandexMusicObject], fetch_children: FetchChildrenType,
) -> BrowseGeneratorReturnType:
    if isinstance(media_content_id, str):
        browse_object = browser.generate_browse_from_media(
            media_content_id,
            fetch_children=False
        )
        if browse_object is None:
            return None
        suffix = browse_object.title
        radio_content_id = f'{browse_object.media_content_type}:{browse_object.media_content_id}'
        thumbnail = browse_object.thumbnail

    elif isinstance(media_content_id, Track):
        suffix = media_content_id.title
        radio_content_id = 'track:' + str(media_content_id.id)
        thumbnail = media_content_id.cover_uri

    elif isinstance(media_content_id, Genre):
        suffix = media_content_id.title
        radio_content_id = 'genre:' + str(media_content_id.id)
        thumbnail = media_content_id.radio_icon.image_url

    elif isinstance(media_content_id, Playlist):
        suffix = media_content_id.title
        radio_content_id = 'playlist:' + str(media_content_id.playlist_id)
        thumbnail = media_content_id.cover.uri

    elif isinstance(media_content_id, Artist):
        suffix = media_content_id.name
        radio_content_id = 'artist:' + str(media_content_id.id)
        thumbnail = media_content_id.cover.uri

    else:
        return None

    thumbnail = sanitize_thumbnail_uri(thumbnail, browser.thumbnail_resolution)
    prefix = browser.get_translation(MEDIA_TYPE_RADIO, 'prefix')

    return BrowseMedia(
        title=f'{prefix}: {suffix}',
        thumbnail=thumbnail,
        media_class=MEDIA_CLASS_TRACK,
        media_content_id=radio_content_id,
        media_content_type=MEDIA_TYPE_RADIO,
        can_play=True,
        can_expand=False
    )


@register_type_browse_processor()
@adapt_directory_to_browse_processor(children_media_class=MEDIA_CLASS_PLAYLIST)
def personal_mixes_processor(browser: 'YandexMusicBrowser', media_id: str) -> Optional[List[Playlist]]:
    landing_root = browser.client.landing('personalplaylists')
    if landing_root and len(landing_root.blocks) > 0:
        blocks_entities = landing_root.blocks[0].entities
        if blocks_entities:
            return [x.data.data for x in blocks_entities]


@register_type_browse_processor()
@adapt_media_id_to_user_id()
@adapt_directory_to_browse_processor(children_media_class=MEDIA_CLASS_DIRECTORY, thumbnail='/blocks/playlist-cover/playlist-cover_like_2x.png')
def user_likes_processor(browser: 'YandexMusicBrowser', media_id: str) -> List[Tuple[str, str]]:
    return [
        ('user_liked_playlists', media_id),
        ('user_liked_artists', media_id),
        ('user_liked_albums', media_id),
        ('user_liked_tracks', media_id),
    ]


@register_type_browse_processor()
@adapt_media_id_to_user_id()
@adapt_directory_to_browse_processor(children_media_class=MEDIA_CLASS_PLAYLIST)
def user_playlists_processor(browser: 'YandexMusicBrowser', media_id: str) -> Optional[List[Playlist]]:
    return browser.client.users_playlists_list(
        user_id=media_id[1:],
        timeout=browser.timeout
    )


@register_type_browse_processor()
@adapt_media_id_to_user_id()
@adapt_directory_to_browse_processor(children_media_class=MEDIA_CLASS_PLAYLIST)
def user_liked_playlists_processor(browser: 'YandexMusicBrowser', media_id: str) -> Optional[List[Playlist]]:
    likes = browser.client.users_likes_playlists(
        user_id=media_id[1:],
        timeout=browser.timeout
    )
    if likes:
        return [x.playlist for x in likes]


@register_type_browse_processor()
@adapt_media_id_to_user_id()
@adapt_directory_to_browse_processor(children_media_class=MEDIA_CLASS_ARTIST)
def user_liked_artists_processor(browser: 'YandexMusicBrowser', media_id: str) -> Optional[List[Artist]]:
    likes = browser.client.users_likes_artists(
        user_id=media_id[1:],
        timeout=browser.timeout
    )
    if likes:
        return [x.artist for x in likes]


@register_type_browse_processor()
@adapt_media_id_to_user_id()
@adapt_directory_to_browse_processor(children_media_class=MEDIA_CLASS_ALBUM)
def user_liked_albums_processor(browser: 'YandexMusicBrowser', media_id: str) -> Optional[List[Album]]:
    likes = browser.client.users_likes_albums(
        user_id=media_id[1:],
        timeout=browser.timeout
    )
    if likes:
        return [x.album for x in likes]


@register_type_browse_processor()
@adapt_media_id_to_user_id()
@adapt_directory_to_browse_processor(children_media_class=MEDIA_CLASS_TRACK)
def user_liked_tracks_processor(browser: 'YandexMusicBrowser', media_id: str) -> Optional[List[Track]]:
    track_list = browser.client.users_likes_tracks(
        user_id=media_id[1:],
        timeout=browser.timeout
    )

    if track_list:
        # @TODO: this method doesn't support timeout, yet...
        return track_list.fetch_tracks()


@register_type_browse_processor()
@adapt_directory_to_browse_processor(children_media_class=MEDIA_CLASS_GENRE)
def genres_processor(browser: 'YandexMusicBrowser', media_id: str):
    items = browser.client.genres(timeout=browser.timeout)
    remove_genre_id = None
    for i, genre in enumerate(items):
        if genre.id == 'all':
            remove_genre_id = i
            break

    if remove_genre_id is not None:
        items.pop(remove_genre_id)

    return items


@register_type_browse_processor()
@adapt_directory_to_browse_processor(children_media_class=MEDIA_CLASS_ALBUM)
def new_releases_processor(browser: 'YandexMusicBrowser', media_id: str) -> Optional[List[Album]]:
    landing_list = browser.client.new_releases(timeout=browser.timeout)
    if landing_list:
        album_ids = landing_list.new_releases
        if album_ids:
            return browser.client.albums(
                album_ids=album_ids,
                timeout=browser.timeout
            )


@register_type_browse_processor()
@adapt_directory_to_browse_processor(children_media_class=MEDIA_CLASS_PLAYLIST)
def new_playlists_processor(browser: 'YandexMusicBrowser', media_id: str) -> Optional[List[Playlist]]:
    landing_list = browser.client.new_playlists(timeout=browser.timeout)
    if landing_list:
        playlist_ids = landing_list.new_playlists
        if playlist_ids:
            # noinspection PyTypeChecker
            return browser.get_playlists_from_ids(playlist_ids)


@register_type_browse_processor()
@adapt_directory_to_browse_processor(children_media_class=MEDIA_CLASS_PLAYLIST)
def yandex_mixes_processor(browser: 'YandexMusicBrowser', media_id: str) -> Optional[List[Playlist]]:
    landing_root = browser.client.landing('mixes')
    if landing_root and len(landing_root.blocks) > 0:
        blocks_entities = landing_root.blocks[0].entities
        if blocks_entities:
            return [x.data for x in blocks_entities]


# @register_hierarchical_menu()
# def popular_artists_processor(browser: 'YandexMusicBrowser', media_id: str):
#     # @TODO
#     pass


# @register_hierarchical_menu()
# def popular_tracks_processor(browser: 'YandexMusicBrowser', media_id: str):
#     # @TODO
#     pass


@adapt_media_browse_processor(str)
def media_type_processor(browser: 'YandexMusicBrowser', media_object: str, fetch_children: FetchChildrenType):
    return media_link_processor(browser, (media_object, None), fetch_children)


@adapt_media_browse_processor(tuple)
def media_link_processor(browser: 'YandexMusicBrowser', media_object: tuple, fetch_children: FetchChildrenType):
    media_content_type, media_content_id = media_object

    if media_content_type in MAP_MEDIA_TYPE_TO_BROWSE:
        browse_generator = MAP_MEDIA_TYPE_TO_BROWSE[media_content_type]

        return browse_generator(
            browser,
            media_content_id,
            fetch_children
        )


@adapt_media_browse_processor(Track)
def track_media_processor(browser: 'YandexMusicBrowser', media_object: Track, fetch_children: FetchChildrenType):
    track_title = f'{media_object.title} — {", ".join(media_object.artists_name())}'
    if media_object.content_warning:
        track_title += u"\U000000A0" * 3 + EXPLICIT_UNICODE_ICON_STANDARD

    show_lyrics = media_object.lyrics_available

    if fetch_children:
        children = []
        if show_lyrics:
            supplement = media_object.get_supplement()
            if supplement:
                lyrics = supplement.lyrics
                if lyrics and lyrics.full_lyrics:
                    for i, line in enumerate(lyrics.full_lyrics.splitlines()):
                        children.append(
                            BrowseMedia(
                                title=line,
                                media_content_id=str(media_object.id) + '_line_' + str(i),
                                media_content_type='lyrics_line',
                                media_class=MEDIA_CLASS_TRACK,
                                can_play=False,
                                can_expand=False,
                                thumbnail=THUMBNAIL_EMPTY_IMAGE,
                            )
                        )
    else:
        children = None

    return BrowseMedia(
        title=track_title,
        media_content_type=MEDIA_TYPE_TRACK,
        media_class=MEDIA_CLASS_TRACK,
        thumbnail=media_object.cover_uri,
        media_content_id=str(media_object.id),
        can_play=True,
        can_expand=show_lyrics,
        children=children
    )


@adapt_media_browse_processor(TrackShort)
def track_short_media_processor(browser: 'YandexMusicBrowser', media_object: TrackShort, fetch_children: FetchChildrenType):
    track = media_object.fetch_track()
    if track:
        return track_media_processor(browser, track, fetch_children)


@adapt_media_browse_processor(Album)
def album_media_processor(browser: 'YandexMusicBrowser', media_object: Album, fetch_children: FetchChildrenType) -> BrowseMedia:
    if fetch_children:
        fetch_children = int(fetch_children) - 1

        children = []
        media_object = media_object.with_tracks(timeout=browser.timeout)
        if media_object.volumes:
            for album_volume in media_object.volumes:
                volume_tracks = browser.generate_browse_list_from_media_list(
                    album_volume,
                    fetch_children=fetch_children,
                )
                children.extend(volume_tracks)

    else:
        children = None

    return BrowseMedia(
        title=media_object.title,
        media_content_type=MEDIA_TYPE_ALBUM,
        media_class=MEDIA_CLASS_ALBUM,
        thumbnail=media_object.cover_uri,
        media_content_id=str(media_object.id),
        can_play=True,
        can_expand=True,
        children=children
    )


@adapt_media_browse_processor(Artist)
def artist_media_processor(browser: 'YandexMusicBrowser', media_object: Artist, fetch_children: FetchChildrenType) -> BrowseMedia:
    if fetch_children:
        fetch_children = int(fetch_children) - 1
        artist_albums = media_object.get_albums(timeout=browser.timeout)

        if artist_albums and artist_albums.albums:
            children = browser.generate_browse_list_from_media_list(
                artist_albums.albums,
                fetch_children=fetch_children,
            )
        else:
            children = []
    else:
        children = None

    return BrowseMedia(
        title=media_object.name,
        media_content_type=MEDIA_TYPE_ARTIST,
        media_class=MEDIA_CLASS_ARTIST,
        thumbnail=media_object.cover.uri,
        children_media_class=MEDIA_CLASS_ALBUM,
        media_content_id=str(media_object.id),
        can_play=False,
        can_expand=True,
        children=children
    )


@adapt_media_browse_processor(Playlist)
def playlist_media_processor(browser: 'YandexMusicBrowser', media_object: Playlist, fetch_children: FetchChildrenType) -> BrowseMedia:
    if fetch_children:
        fetch_children = int(fetch_children) - 1
        playlist_tracks = media_object.fetch_tracks(timeout=browser.timeout)
        children = browser.generate_browse_list_from_media_list(
            playlist_tracks,
            fetch_children=fetch_children,
        )
    else:
        children = None

    return BrowseMedia(
        title=media_object.title,
        media_content_type=MEDIA_TYPE_PLAYLIST,
        media_class=MEDIA_CLASS_PLAYLIST,
        thumbnail=media_object.animated_cover_uri or media_object.cover.uri,
        media_content_id=f'{media_object.owner.uid}:{media_object.kind}',
        can_play=True,
        can_expand=True,
        children_media_class=MEDIA_CLASS_TRACK,
        children=children
    )


@adapt_media_browse_processor(MixLink)
def mix_link_media_processor(browser: 'YandexMusicBrowser', media_object: MixLink, fetch_children: FetchChildrenType) -> Optional[BrowseMedia]:
    if not media_object.url.startswith('/tag/'):
        # @TODO: support other MixLink types
        return None

    mix_link_tag = media_object.url[5:]
    if '?' in mix_link_tag:
        mix_link_tag = mix_link_tag.split('?')[0]
    if mix_link_tag.endswith('/'):
        mix_link_tag = media_object[:-1]

    if fetch_children:
        fetch_children = int(fetch_children) - 1
        children = []
        mix_link_playlists = media_object.client.tags(mix_link_tag, timeout=browser.timeout)
        if mix_link_playlists and mix_link_playlists.ids:
            playlists = browser.get_playlists_from_ids(mix_link_playlists.ids)
            if playlists:
                children = browser.generate_browse_list_from_media_list(
                    playlists,
                    fetch_children=fetch_children
                )
    else:
        children = None

    return BrowseMedia(
        title=media_object.title,
        media_content_type=MEDIA_TYPE_MIX_TAG,
        media_class=MEDIA_CLASS_DIRECTORY,
        thumbnail=media_object.background_image_uri or media_object.cover_uri or media_object.cover_white,
        media_content_id=mix_link_tag,
        can_play=False,
        can_expand=True,
        children_media_class=MEDIA_CLASS_PLAYLIST,
        children=children
    )


@adapt_media_browse_processor(TagResult)
def tag_result_media_processor(browser: 'YandexMusicBrowser', media_object: TagResult, fetch_children: FetchChildrenType):
    # noinspection PyTypeChecker
    tag: Tag = media_object.tag

    if fetch_children:
        playlists = browser.get_playlists_from_ids(media_object.ids)
        children = browser.generate_browse_list_from_media_list(
            playlists,
            fetch_children=fetch_children,
        )
    else:
        children = None

    return BrowseMedia(
        title=tag.name,
        media_content_type=MEDIA_TYPE_MIX_TAG,
        media_class=MEDIA_CLASS_DIRECTORY,
        thumbnail=tag.og_image,
        media_content_id=tag.id,
        can_play=False,
        can_expand=True,
        children_media_class=MEDIA_CLASS_PLAYLIST,
        children=children,
    )


@adapt_media_browse_processor(Genre)
def genre_media_processor(browser: 'YandexMusicBrowser', media_object: Genre, fetch_children: FetchChildrenType):
    if media_object.radio_icon:
        thumbnail = media_object.radio_icon.image_url
    elif media_object.images:
        thumbnail = getattr(media_object.images, '_300x300', None)
        if thumbnail is None:
            thumbnail = getattr(media_object.images, '_208x208', None)
    else:
        thumbnail = None
        
    if fetch_children:
        fetch_children = int(fetch_children) - 1
        
        children = [
            generate_radio_object(
                browser,
                media_object,
                fetch_children=fetch_children
            )
        ]

        if media_object.sub_genres:
            children.extend(
                browser.generate_browse_list_from_media_list(
                    (media_object.sub_genres
                     if browser.show_hidden else
                     filter(lambda x: x.show_in_menu, media_object.sub_genres)),
                    fetch_children=fetch_children
                )
            )

        genre_playlists = browser.client.tags(
            media_object.id,
            timeout=browser.timeout
        )

        if genre_playlists.tag is None and 'en' in media_object.titles:
            # Workaround for tags with bad IDs
            genre_playlists = browser.client.tags(
                media_object.titles['en'].title,
                timeout=browser.timeout
            )

        if genre_playlists and genre_playlists.ids:
            playlists = browser.get_playlists_from_ids(genre_playlists.ids)
            if playlists:
                children.extend(
                    browser.generate_browse_list_from_media_list(
                        playlists,
                        fetch_children=fetch_children
                    )
                )
    else:
        children = None

    return BrowseMedia(
        title=media_object.title,
        media_content_type=MEDIA_TYPE_GENRE,
        media_content_id=media_object.id,
        media_class=MEDIA_CLASS_DIRECTORY,
        thumbnail=thumbnail,
        can_play=False,
        can_expand=True,
        children_media_class=MEDIA_CLASS_PLAYLIST,
        children=children
    )


@register_type_browse_processor(MEDIA_TYPE_ALBUM, media_id_pattern=r'\d+')
@adapt_type_to_browse_processor()
def album_type_processor(browser: 'YandexMusicBrowser', media_content_id: MediaContentIDType) -> Optional[Album]:
    albums = browser.client.albums(
        album_ids=media_content_id,
        timeout=browser.timeout
    )
    if albums:
        return albums[0]


@register_type_browse_processor(MEDIA_TYPE_ARTIST, media_id_pattern=r'\d+')
@adapt_type_to_browse_processor()
def artist_type_processor(browser: 'YandexMusicBrowser', media_content_id: MediaContentIDType) -> Optional[Artist]:
    artists = browser.client.artists(
        artist_ids=media_content_id,
        timeout=browser.timeout
    )
    if artists:
        return artists[0]


@register_type_browse_processor(MEDIA_TYPE_PLAYLIST, media_id_pattern=r'(\d+:)?\d+')
@adapt_type_to_browse_processor()
def playlist_type_processor(browser: 'YandexMusicBrowser', media_content_id: MediaContentIDType) -> Optional[Playlist]:
    parts = media_content_id.split(':')
    kind = parts[-1]
    playlist_user_id = parts[0] if len(parts) > 1 else None

    return browser.client.users_playlists(
        kind=kind,
        user_id=playlist_user_id,
        timeout=browser.timeout
    )


@register_type_browse_processor(MEDIA_TYPE_TRACK, media_id_pattern=r'\d+')
@adapt_type_to_browse_processor()
def track_type_processor(browser: 'YandexMusicBrowser', media_content_id: MediaContentIDType) -> Optional[Track]:
    tracks = browser.client.tracks(
        track_ids=media_content_id,
        timeout=browser.timeout
    )
    if tracks:
        return tracks[0]


@register_type_browse_processor(MEDIA_TYPE_MIX_TAG)
@adapt_type_to_browse_processor()
def mix_tag_type_processor(browser: 'YandexMusicBrowser', media_content_id: MediaContentIDType) -> Optional[TagResult]:
    return browser.client.tags(
        tag_id=media_content_id,
        timeout=browser.timeout
    )


@register_type_browse_processor(MEDIA_TYPE_GENRE)
@adapt_type_to_browse_processor()
def genre_type_processor(browser: 'YandexMusicBrowser', media_content_id: MediaContentIDType) -> Optional[Genre]:
    genres = browser.client.genres(timeout=browser.timeout)
    return find_genre_recursive(media_content_id, genres)


YandexMusicBrowser.DEFAULT_MENU_OPTIONS = BrowseTree.from_map({
    'items': [
        "user_playlists",
        "personal_mixes",
        "user_likes",
        "yandex_mixes",
        "genres",
        # "popular_artists",
        # "popular_tracks",
        "new_releases",
        "new_playlists"
    ]
}, validate=True)
