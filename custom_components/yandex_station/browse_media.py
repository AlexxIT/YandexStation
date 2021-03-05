"""Support for media browsing."""
__all__ = [
    "MEDIA_TYPES_MENU_MAPPING",
    "YandexMusicBrowser",
]

import logging
from time import time
from typing import Union, Optional, Iterable, List, Dict, Tuple, Mapping, Any

from homeassistant.components.media_player import BrowseError, BrowseMedia
from homeassistant.components.media_player.const import MEDIA_CLASS_PLAYLIST, MEDIA_CLASS_ARTIST, MEDIA_CLASS_ALBUM, \
    MEDIA_CLASS_TRACK, MEDIA_CLASS_GENRE, MEDIA_TYPE_PLAYLIST, MEDIA_TYPE_ALBUM, MEDIA_TYPE_ARTIST, \
    MEDIA_TYPE_TRACK, MEDIA_CLASS_DIRECTORY
from homeassistant.const import CONF_TIMEOUT
from yandex_music import Client, TracksList, TrackShort, Track, Playlist, Artist, Album, MixLink, PlaylistId, \
    TagResult, Tag, Genre
from yandex_music.exceptions import TimedOut

from custom_components.yandex_station.const import ROOT_MEDIA_CONTENT_TYPE, CONF_LANGUAGE, \
    CONF_CACHE_TTL, CONF_ROOT_OPTIONS, CONF_THUMBNAIL_RESOLUTION, CONF_WIDTH, CONF_HEIGHT, \
    EXPLICIT_UNICODE_ICON_STANDARD, MEDIA_TYPE_MIX_TAG, MEDIA_TYPE_GENRE, CONF_SHOW_HIDDEN, MEDIA_TYPE_RADIO

_LOGGER = logging.getLogger(__name__)

DEFAULT_TITLE_LANGUAGE = "en"
DEFAULT_REQUEST_TIMEOUT = 15

ITEM_RESPONSE_CACHE = {}


MEDIA_TYPES_MENU_MAPPING = {
    "current_user_playlists": {
        "title": {
            "en": "My playlists",
            "ru": "Мои плейлисты",
        },
        "sort_children": True,
        "children_media_class": MEDIA_CLASS_PLAYLIST,
    },
    "current_user_personal_mixes": {
        "title": {
            "en": "Personal mixes",
            "ru": "Персональные подборки",
        },
        "sort_children": False,
        "children_media_class": MEDIA_CLASS_PLAYLIST,
    },
    "yandex_mixes": {
        "title": {
            "en": "Yandex mixes",
            "ru": "Подборки Яндекса",
        },
        "sort_children": False,
        "children_media_class": MEDIA_CLASS_DIRECTORY,
    },
    "current_user_liked_artists": {
        "title": {
            "en": "Liked artists",
            "ru": "Понравившиеся исполнители",
        },
        "children_media_class": MEDIA_CLASS_ARTIST,
    },
    "current_user_liked_albums": {
        "title": {
            "en": "Liked albums",
            "ru": "Понравившиеся альбомы",
        },
        "children_media_class": MEDIA_CLASS_ALBUM,
    },
    "current_user_liked_tracks": {
        "title": {
            "en": "Liked tracks",
            "ru": "Понравившиеся треки",
        },
        "children_media_class": MEDIA_CLASS_TRACK,
    },
    "current_user_liked_playlists": {
        "title": {
            "en": "Liked playlists",
            "ru": "Понравившиеся плейлисты",
        },
        "children_media_class": MEDIA_CLASS_PLAYLIST,
    },
    "current_user_likes": {
        "title": {
            "en": "Preferences",
            "ru": "Понравившееся",
        },
        "children_media_class": MEDIA_CLASS_DIRECTORY,
        "children": [
            "current_user_liked_playlists",
            "current_user_liked_tracks",
            "current_user_liked_albums",
            "current_user_liked_artists",
        ],
        "thumbnail": "/blocks/playlist-cover/playlist-cover_like_2x.png",
    },
    # "current_user_liked_podcasts": "Liked podcasts", MEDIA_CLASS_PODCAST),
    "popular_artists": {
        "title": {
            "en": "Top artists",
            "ru": "Популярные исполнители",
        },
        "children_media_class": MEDIA_CLASS_ARTIST,
    },
    "popular_tracks": {
        "title": {
            "en": "Top tracks",
            "ru": "Популярные треки",
        },
        "children_media_class": MEDIA_CLASS_TRACK,
    },
    "genres": {
        "title": {
            "en": "Music genres",
            "ru": "Жанры",
        },
        "children_media_class": MEDIA_CLASS_GENRE,
    },
    "new_releases": {
        "title": {
            "en": "New releases",
            "ru": "Новые альбомы",
        },
        "children_media_class": MEDIA_CLASS_ALBUM,
    },
    "new_playlists": {
        "title": {
            "en": "New playlists",
            "ru": "Новые плейлисты",
        },
        "children_media_class": MEDIA_CLASS_PLAYLIST,
    },
}

CLASS_TYPE_MAP = {
    Track: MEDIA_CLASS_TRACK,
    Playlist: MEDIA_CLASS_PLAYLIST,
    TracksList: MEDIA_CLASS_DIRECTORY,
    Artist: MEDIA_CLASS_ARTIST,
    Album: MEDIA_CLASS_ALBUM,
}


class MissingMediaInformation(BrowseError):
    """Missing media required information."""


class UnknownMediaType(BrowseError):
    """Unknown media type."""


class TimeoutDataFetching(BrowseError):
    """Timed out while fetching data"""


MediaObjectType = Union[TrackShort, Track, Album, Artist, Playlist, Genre, MixLink, TagResult]


LANGUAGE_RADIO_PREFIX = {
    'en': 'Radio',
    'ru': 'Радио',
}


class YandexMusicBrowser:
    _default_cache_ttl = 600
    _default_timeout = 15
    _default_language = 'ru'
    _default_root_options = (
        "current_user_playlists",
        "current_user_personal_mixes",
        "current_user_likes",
        "yandex_mixes",
        "genres",
        # "popular_artists",
        # "popular_tracks",
        "new_releases",
        "new_playlists",
    )
    _default_thumbnail_resolution = (200, 200)
    _default_show_hidden = False

    def __init__(
            self,
            authentication: Union[Tuple[str, str], str, Client],
            browser_config: Optional[Mapping[str, Any]] = None,
    ):
        if isinstance(authentication, Client):
            client = authentication
        elif isinstance(authentication, str):
            client = Client.from_token(authentication)
        elif isinstance(authentication, tuple):
            client = Client.from_credentials(*authentication)
        else:
            raise TypeError('invalid authentication method provided')

        self.client = client

        self._cache_ttl = None
        self._timeout = None
        self._root_options = None
        self._thumbnail_resolution = None
        self._show_hidden = None
        self.browser_config = browser_config

        self._response_cache = {}

    @property
    def show_hidden(self) -> bool:
        return (self._default_show_hidden
                if self._show_hidden is None
                else self._show_hidden)

    @show_hidden.setter
    def show_hidden(self, value: Optional[bool]):
        self._show_hidden = value

    @property
    def cache_ttl(self) -> Union[int, float]:
        return (self._default_cache_ttl
                if self._cache_ttl is None
                else self._cache_ttl)

    @cache_ttl.setter
    def cache_ttl(self, value: Optional[Union[int, float]]):
        self._cache_ttl = value

    @property
    def root_options(self) -> Tuple[str]:
        return (self._default_root_options
                if self._root_options is None
                else self._root_options)

    @root_options.setter
    def root_options(self, value: Optional[Iterable[str]]):
        self._root_options = value

    @property
    def thumbnail_resolution(self) -> Tuple[int, int]:
        return (self._default_thumbnail_resolution
                if self._thumbnail_resolution is None
                else self._thumbnail_resolution)

    @thumbnail_resolution.setter
    def thumbnail_resolution(self, value: Optional[Tuple[int, int]]):
        self._thumbnail_resolution = value

    @property
    def browser_config(self):
        browser_config = {
            CONF_LANGUAGE: self.language,
        }

        if self._cache_ttl is not None:
            browser_config[CONF_CACHE_TTL] = self._cache_ttl

        if self._timeout is not None:
            browser_config[CONF_TIMEOUT] = self._cache_ttl

        if self._root_options is not None:
            browser_config[CONF_ROOT_OPTIONS] = self._root_options

        if self._thumbnail_resolution is not None:
            browser_config[CONF_THUMBNAIL_RESOLUTION] = {
                CONF_WIDTH: self._thumbnail_resolution[0],
                CONF_HEIGHT: self._thumbnail_resolution[1]
            }

        if self._show_hidden is not None:
            browser_config[CONF_SHOW_HIDDEN] = self._show_hidden

        return browser_config
    
    @browser_config.setter
    def browser_config(self, browser_config: Optional[Mapping[str, Any]]):
        browser_config = browser_config or {}
        self.cache_ttl = browser_config.get(CONF_CACHE_TTL)
        self.timeout = browser_config.get(CONF_TIMEOUT)
        self.language = browser_config.get(CONF_LANGUAGE)
        self.root_options = browser_config.get(CONF_ROOT_OPTIONS)
        self.show_hidden = browser_config.get(CONF_SHOW_HIDDEN)

        thumbnail_resolution = browser_config.get(CONF_THUMBNAIL_RESOLUTION)
        if thumbnail_resolution is not None:
            self.thumbnail_resolution = (
                thumbnail_resolution[CONF_WIDTH],
                thumbnail_resolution[CONF_HEIGHT]
            )

    @property
    def user_id(self) -> str:
        return str(self.client.me.account.uid)

    @property
    def language(self) -> str:
        return self.client.request.headers['Accept-Language']

    @language.setter
    def language(self, language: str) -> None:
        self.client.request.set_language(language)

    @property
    def response_cache(self) -> dict:
        return self._response_cache

    @classmethod
    def process_thumbnail(cls, thumbnail: str):
        if '%%' in thumbnail:
            thumbnail = thumbnail.replace('%%', '200x200')
        if thumbnail.startswith('/'):
            thumbnail = 'https://music.yandex.ru' + thumbnail
        elif not thumbnail.startswith(('http://', 'https://')):
            thumbnail = 'https://' + thumbnail
        return thumbnail

    @classmethod
    def find_genre(cls, genre_id: str, genres: List[Genre]) -> Optional[Genre]:
        for genre in genres:
            if genre.id == genre_id:
                return genre
            if genre.sub_genres:
                sub_genre = cls.find_genre(genre_id, genre.sub_genres)
                if sub_genre:
                    return sub_genre

    def generate_radio_object(
            self,
            media_object: MediaObjectType,
            cloud_compatible: bool = False,
    ):
        if isinstance(media_object, Track):
            suffix = media_object.title
            radio_content_id = 'track:' + str(media_object.id)
            thumbnail = media_object.cover_uri
        elif isinstance(media_object, Genre):
            suffix = media_object.title
            radio_content_id = 'genre:' + str(media_object.id)
            thumbnail = media_object.radio_icon.image_url
        elif isinstance(media_object, Playlist):
            suffix = media_object.title
            radio_content_id = 'playlist:' + str(media_object.playlist_id)
            thumbnail = media_object.cover.uri
        elif isinstance(media_object, Artist):
            suffix = media_object.name
            radio_content_id = 'artist:' + str(media_object.id)
            thumbnail = media_object.cover.uri
        else:
            return None

        thumbnail = self.process_thumbnail(thumbnail)


        prefix = LANGUAGE_RADIO_PREFIX.get(self.language, LANGUAGE_RADIO_PREFIX.get(self._default_language, 'Radio'))
        return BrowseMedia(
            title=f'{prefix}: {suffix}',
            thumbnail=thumbnail,
            media_class=MEDIA_CLASS_TRACK,
            media_content_id=radio_content_id,
            media_content_type=MEDIA_TYPE_RADIO,
            can_play=not cloud_compatible,
            can_expand=False,
        )

    def generate_browse_media_object(
            self,
            media_object: MediaObjectType,
            cloud_compatible: bool = False,
            with_children: bool = False,
            sort_children: bool = True,
            payload: Optional[dict] = None,
    ) -> Optional[BrowseMedia]:
        """
        Generate Home Assistant BrowseMedia object for Yandex model.
        """
        if isinstance(media_object, TrackShort):
            media_object = media_object.fetch_track()

        params = {}

        if isinstance(media_object, Track):
            track_title = f'{media_object.title} — {", ".join(media_object.artists_name())}'
            if media_object.content_warning:
                track_title += u"\U000000A0" * 3 + EXPLICIT_UNICODE_ICON_STANDARD

            params.update({
                "title": track_title,
                "media_content_type": MEDIA_TYPE_TRACK,
                "media_class": MEDIA_CLASS_TRACK,
                "thumbnail": media_object.cover_uri,
                "media_content_id": str(media_object.id),
                "can_play": True,
                "can_expand": False,
            })

        elif isinstance(media_object, Album):
            params.update({
                "title": media_object.title,
                "media_content_type": MEDIA_TYPE_ALBUM,
                "media_class": MEDIA_CLASS_ALBUM,
                "thumbnail": media_object.cover_uri,
                "media_content_id": str(media_object.id),
                "can_play": True,
                "can_expand": True,
            })
            if with_children:
                children = []
                params["children"] = children
                media_object = media_object.with_tracks(timeout=self.timeout)
                if media_object.volumes:
                    for album_volume in media_object.volumes:
                        volume_tracks = self.generate_browse_media_objects_from_list(
                            album_volume,
                            cloud_compatible=cloud_compatible,
                            with_children=False,
                            sort_children=sort_children,
                        )
                        children.extend(volume_tracks)

        elif isinstance(media_object, Artist):
            params.update({
                "title": media_object.name,
                "media_content_type": MEDIA_TYPE_ARTIST,
                "media_class": MEDIA_CLASS_ARTIST,
                "thumbnail": media_object.cover.uri,
                "children_media_class": MEDIA_CLASS_ALBUM,
                "media_content_id": str(media_object.id),
                "can_play": False,
                "can_expand": True,
            })
            if with_children:
                artist_albums = media_object.get_albums(timeout=self.timeout)
                params["children"] = self.generate_browse_media_objects_from_list(
                    artist_albums,
                    cloud_compatible=cloud_compatible,
                    with_children=False,
                    sort_children=sort_children,
                )

        elif isinstance(media_object, Playlist):
            params.update({
                "title": media_object.title,
                "media_content_type": MEDIA_TYPE_PLAYLIST,
                "media_class": MEDIA_CLASS_PLAYLIST,
                "thumbnail": media_object.cover.uri,
                "media_content_id": f'{media_object.owner.uid}:{media_object.kind}',
                "can_play": (not cloud_compatible
                             or str(media_object.owner.uid) == self.user_id),
                "can_expand": True,
            })
            if with_children:
                playlist_tracks = media_object.fetch_tracks(timeout=self.timeout)
                params["children"] = self.generate_browse_media_objects_from_list(
                    playlist_tracks,
                    cloud_compatible=cloud_compatible,
                    with_children=False,
                    sort_children=sort_children,
                )

        elif isinstance(media_object, MixLink):
            if not media_object.url.startswith('/tag/'):
                return None

            mix_link_tag = media_object.url[5:]
            if '?' in mix_link_tag:
                mix_link_tag = mix_link_tag.split('?')[0]
            if mix_link_tag.endswith('/'):
                mix_link_tag = media_object[:-1]

            params.update({
                "title": media_object.title,
                "media_content_type": MEDIA_TYPE_MIX_TAG,
                "media_class": MEDIA_CLASS_DIRECTORY,
                "thumbnail": media_object.background_image_uri or media_object.cover_uri or media_object.cover_white,
                "media_content_id": mix_link_tag,
                "can_play": False,
                "can_expand": True,
            })
            if with_children:
                mix_link_playlists = media_object.client.tags(mix_link_tag, timeout=self.timeout)
                params["children"] = []
                if mix_link_playlists and mix_link_playlists.ids:
                    playlists = self.get_playlists_from_ids(mix_link_playlists.ids)
                    if playlists:
                        params["children"] = self.generate_browse_media_objects_from_list(
                            playlists,
                            cloud_compatible=cloud_compatible,
                            with_children=False,
                            sort_children=False,
                        )

        elif isinstance(media_object, TagResult):
            # noinspection PyTypeChecker
            tag: Tag = media_object.tag

            params.update({
                "title": tag.name,
                "media_content_type": MEDIA_TYPE_MIX_TAG,
                "media_class": MEDIA_CLASS_DIRECTORY,
                "thumbnail": tag.og_image,
                "media_content_id": tag.id,
                "can_play": False,
                "can_expand": True,
            })
            if with_children:
                playlists = self.get_playlists_from_ids(media_object.ids)
                params["children"] = self.generate_browse_media_objects_from_list(
                    playlists,
                    cloud_compatible=cloud_compatible,
                    with_children=False,
                    sort_children=False,
                )

        elif isinstance(media_object, Genre):
            if media_object.radio_icon:
                params["thumbnail"] = media_object.radio_icon.image_url
            elif media_object.images:
                params["thumbnail"] = getattr(media_object.images, '_300x300', None)

            params.update({
                "title": media_object.title,
                "media_content_type": MEDIA_TYPE_GENRE,
                "media_content_id": media_object.id,
                "media_class": MEDIA_CLASS_DIRECTORY,
                "can_play": False,
                "can_expand": True,
            })

            if with_children:
                children = [self.generate_radio_object(media_object, cloud_compatible=cloud_compatible)]
                if media_object.sub_genres:
                    children.extend(
                        self.generate_browse_media_objects_from_list(
                            (media_object.sub_genres
                             if self.show_hidden else
                             filter(lambda x: x.show_in_menu, media_object.sub_genres)),
                            cloud_compatible=cloud_compatible,
                            with_children=False,
                            sort_children=False,
                        )
                    )

                genre_playlists = self.client.tags(
                    media_object.id,
                    timeout=self.timeout
                )
                if genre_playlists.tag is None and 'en' in media_object.titles:
                    # Workaround for tags with bad IDs
                    genre_playlists = self.client.tags(
                        media_object.titles['en'].title,
                        timeout=self.timeout
                    )

                if genre_playlists and genre_playlists.ids:
                    playlists = self.get_playlists_from_ids(genre_playlists.ids)
                    if playlists:
                        children.extend(
                            self.generate_browse_media_objects_from_list(
                                playlists,
                                cloud_compatible=cloud_compatible,
                                with_children=False,
                                sort_children=False,
                            )
                        )

                params["children"] = children

        else:
            return None

        if payload:
            params.update(payload)

        if params.get("thumbnail") is not None:
            params["thumbnail"] = self.process_thumbnail(params["thumbnail"])

        return BrowseMedia(**params)

    def generate_browse_media_objects_from_list(
            self,
            source_list: Iterable[MediaObjectType],
            cloud_compatible: bool = False,
            with_children: bool = False,
            sort_children: bool = True,
    ) -> List[BrowseMedia]:
        generated_objects = []
        for media_object in source_list:
            generated_object = self.generate_browse_media_object(
                media_object,
                cloud_compatible=cloud_compatible,
                with_children=with_children,
                sort_children=sort_children,
            )

            if generated_object is None:
                continue

            generated_objects.append(generated_object)

        if sort_children:
            return sorted(generated_objects, key=lambda x: x.title)
        return generated_objects

    def get_playlists_from_ids(
            self,
            playlist_ids: List[Union[Dict[str, Union[int, str]], PlaylistId]],
            *args, **kwargs
    ):
        # noinspection PyUnresolvedReferences
        playlist_ids = [
            playlist if isinstance(playlist_ids, str) else f'{playlist["uid"]}:{playlist["kind"]}'
            for playlist in playlist_ids
        ]
        return self.client.playlists_list(playlist_ids=playlist_ids, *args, **kwargs)

    def get_translated_title(self, config: dict) -> Optional[str]:
        if "title" not in config:
            return None
        return config["title"].get(
            self.language,
            config["title"].get(
                self._default_language,
                "[UNKNOWN TITLE]"
            )
        )

    def generate_browse_media_menu(
            self,
            media_content_id: str,
            media_content_type: str,
            config: dict,
            cloud_compatible: bool = False,
            with_children: bool = True,
    ):
        children = None
        if with_children and 'children' in config:
            children = []
            for sub_media_content_type in config['children']:
                if isinstance(sub_media_content_type, tuple):
                    children.append(
                        self.build_item_response(
                            media_content_id=sub_media_content_type[1],
                            media_content_type=sub_media_content_type[0],
                            cloud_compatible=cloud_compatible,
                            with_children=False,
                        )
                    )

                elif callable(sub_media_content_type):
                    result = sub_media_content_type(self)
                    if result:
                        children.append(result)

                else:
                    config = MEDIA_TYPES_MENU_MAPPING.get(sub_media_content_type)
                    if not config:
                        _LOGGER.debug('Invalid submenu "%s" for menu "%s"', sub_media_content_type, media_content_type)
                        continue

                    children.append(self.generate_browse_media_menu(
                        media_content_id=sub_media_content_type,
                        media_content_type=sub_media_content_type,
                        config=config,
                        cloud_compatible=cloud_compatible,
                        with_children=False,
                    ))

        return BrowseMedia(
            title=self.get_translated_title(config),
            media_class=config.get("media_class", MEDIA_CLASS_DIRECTORY),
            media_content_type=media_content_id,
            media_content_id=media_content_type,
            can_expand=True,
            can_play=False,
            children_media_class=config.get("children_media_class"),
            children=children,
            thumbnail=self.process_thumbnail(config["thumbnail"]) if config.get("thumbnail") else None,
        )

    def cache_garbage_collection(self):
        """Clear cache entries that are outdated."""
        now = time()
        for cache_key in list(ITEM_RESPONSE_CACHE.keys()):
            if (now - ITEM_RESPONSE_CACHE[cache_key][0]) > self.cache_ttl:
                del ITEM_RESPONSE_CACHE[cache_key]

    def build_item_response(
            self,
            media_content_type: str,
            media_content_id: str,
            cloud_compatible: bool = False,
            with_children: bool = True,
            sort_children: Optional[bool] = None,
    ) -> BrowseMedia:
        config = MEDIA_TYPES_MENU_MAPPING.get(media_content_type, {})

        _LOGGER.debug('Building response: %s / %s', media_content_type, media_content_id)

        cache_key = None
        cache_enabled = self.cache_ttl > 0
        if cache_enabled:
            self.cache_garbage_collection()

            # Check if cache has entry for current request
            cache_key = (media_content_type, media_content_id, cloud_compatible)
            if cache_key in ITEM_RESPONSE_CACHE:
                return ITEM_RESPONSE_CACHE[cache_key][1]

        try:
            music_client = self.client
            media = None
            if media_content_type == MEDIA_TYPE_ALBUM:
                albums = music_client.albums(album_ids=media_content_id, timeout=self.timeout)
                if albums:
                    media = albums[0]

            elif media_content_type == MEDIA_TYPE_ARTIST:
                artists = music_client.artists(artist_ids=media_content_id, timeout=self.timeout)
                if artists:
                    media = artists[0]

            elif media_content_type == MEDIA_TYPE_PLAYLIST:
                parts = media_content_id.split(':')
                kind = parts[-1]
                if len(parts) == 1:
                    user_id = None
                elif len(parts) == 2:
                    user_id = parts[0]
                else:
                    _LOGGER.error("Invalid playlist ID received: %s", media_content_id)
                    raise MissingMediaInformation

                media = music_client.users_playlists(user_id=user_id, kind=kind, timeout=self.timeout)

            elif media_content_type == MEDIA_TYPE_TRACK:
                media = music_client.tracks(track_ids=media_content_id, timeout=self.timeout)

            elif media_content_type == MEDIA_TYPE_MIX_TAG:
                media = music_client.tags(tag_id=media_content_id, timeout=self.timeout)

            elif media_content_type == MEDIA_TYPE_GENRE:
                genres = music_client.genres()
                media = self.find_genre(media_content_id, genres)

            else:
                items = None

                if media_content_type == "current_user_playlists":
                    items = music_client.users_playlists_list(timeout=self.timeout)

                elif media_content_type == "current_user_personal_mixes":
                    landing_root = music_client.landing('personalplaylists')
                    if landing_root and len(landing_root.blocks) > 0:
                        blocks_entities = landing_root.blocks[0].entities
                        if blocks_entities:
                            items = [x.data.data for x in blocks_entities]

                elif media_content_type == "current_user_liked_playlists":
                    likes = music_client.users_likes_playlists(timeout=self.timeout)
                    if likes:
                        items = [x.playlist for x in likes]

                elif media_content_type == "current_user_liked_artists":
                    likes = music_client.users_likes_artists(timeout=self.timeout)
                    if likes:
                        items = [x.artist for x in likes]

                elif media_content_type == "current_user_liked_albums":
                    likes = music_client.users_likes_albums(timeout=self.timeout)
                    if likes:
                        items = [x.album for x in likes]

                elif media_content_type == "current_user_liked_tracks":
                    track_list = music_client.users_likes_tracks(timeout=self.timeout)
                    if track_list:
                        # @TODO: this method doesn't support timeout, yet...
                        items = track_list.fetch_tracks()

                elif media_content_type == "new_releases":
                    landing_list = music_client.new_releases(timeout=self.timeout)
                    if landing_list:
                        album_ids = landing_list.new_releases
                        if album_ids:
                            items = music_client.albums(album_ids=album_ids, timeout=self.timeout)

                elif media_content_type == "new_playlists":
                    landing_list = music_client.new_playlists(timeout=self.timeout)
                    if landing_list:
                        playlist_ids = landing_list.new_playlists
                        if playlist_ids:
                            # noinspection PyTypeChecker
                            items = self.get_playlists_from_ids(playlist_ids)

                elif media_content_type == "yandex_mixes":
                    landing_root = music_client.landing('mixes')
                    if landing_root and len(landing_root.blocks) > 0:
                        blocks_entities = landing_root.blocks[0].entities
                        if blocks_entities:
                            items = [x.data for x in blocks_entities]

                elif media_content_type == "popular_artists":
                    # @TODO
                    pass

                elif media_content_type == "popular_tracks":
                    # @TODO
                    pass

                elif media_content_type == "genres":
                    items = music_client.genres(timeout=self.timeout)
                    remove_genre_id = None
                    for i, genre in enumerate(items):
                        if genre.id == 'all':
                            remove_genre_id = i
                            break

                    if remove_genre_id is not None:
                        items.pop(remove_genre_id)

                elif media_content_type in MEDIA_TYPES_MENU_MAPPING:
                    return self.generate_browse_media_menu(
                        media_content_id=media_content_id,
                        media_content_type=media_content_type,
                        config=MEDIA_TYPES_MENU_MAPPING[media_content_type],
                        cloud_compatible=cloud_compatible,
                        with_children=with_children,
                    )

                else:
                    _LOGGER.debug('Unknown media type')
                    raise UnknownMediaType

                if with_children:
                    if sort_children is None:
                        sort_children = config.get("sort_children", False)

                    children = self.generate_browse_media_objects_from_list(
                        items,
                        cloud_compatible=cloud_compatible,
                        with_children=False,
                        sort_children=sort_children,
                    ) if items else None
                else:
                    children = None

                browse_media_object = BrowseMedia(
                    title=self.get_translated_title(config),
                    media_class=config.get("media_class", MEDIA_CLASS_DIRECTORY),
                    media_content_id=media_content_id,
                    media_content_type=media_content_type,
                    can_play=False,
                    can_expand=True,
                    children_media_class=config.get("children_media_class"),
                    children=children,
                )

                if cache_enabled:
                    ITEM_RESPONSE_CACHE[cache_key] = (time(), browse_media_object)

                return browse_media_object

            if media is None:
                _LOGGER.debug('Unknown media: %s(%s)', media_content_type, media_content_id)
                raise UnknownMediaType

            browse_media_object = self.generate_browse_media_object(
                media,
                cloud_compatible=cloud_compatible,
                with_children=with_children,
                sort_children=False,
            )

            if cache_enabled:
                ITEM_RESPONSE_CACHE[cache_key] = (time(), browse_media_object)

            return browse_media_object

        except TimedOut:
            raise TimeoutDataFetching(f'Timed out while fetching {media_content_type} / {media_content_id}') from None

        except Exception:
            if cache_key in ITEM_RESPONSE_CACHE:
                del ITEM_RESPONSE_CACHE[cache_key]
            raise

    def build_root_response(self, cloud_compatible: bool = False):
        return self.generate_browse_media_menu(
            media_content_type=ROOT_MEDIA_CONTENT_TYPE,
            media_content_id=ROOT_MEDIA_CONTENT_TYPE,
            with_children=True,
            config={
                "title": {
                    "en": "Media Library",
                    "ru": "Библиотека",
                },
                "sort_children": False,
                "children_media_class": MEDIA_CLASS_DIRECTORY,
                "children": self.root_options,
            },
            cloud_compatible=cloud_compatible,
        )
