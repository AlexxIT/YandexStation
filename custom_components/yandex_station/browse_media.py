"""Support for media browsing."""
import logging
from time import time
from typing import Union, Optional, Iterable, List, Dict

from homeassistant.components.media_player import BrowseError, BrowseMedia
from homeassistant.components.media_player.const import MEDIA_CLASS_PLAYLIST, MEDIA_CLASS_ARTIST, MEDIA_CLASS_ALBUM, \
    MEDIA_CLASS_TRACK, MEDIA_CLASS_GENRE, MEDIA_TYPE_PLAYLIST, MEDIA_TYPE_ALBUM, MEDIA_TYPE_ARTIST, \
    MEDIA_TYPE_TRACK, MEDIA_CLASS_DIRECTORY
from yandex_music import Client, TracksList, TrackShort, Track, Playlist, Artist, Album, MixLink, PlaylistId, \
    TagResult, Tag, Genre
from yandex_music.exceptions import TimedOut

_LOGGER = logging.getLogger(__name__)

MEDIA_TYPE_PODCAST = "podcast"
MEDIA_TYPE_MIX_TAG = "mix_tag"
MEDIA_TYPE_GENRE = "genre"

ROOT_MEDIA_CONTENT_TYPE = "library"

DEFAULT_TITLE_LANGUAGE = "ru"
DEFAULT_SORT_CHILDREN = False
DEFAULT_REQUEST_TIMEOUT = 15

EXPLICIT_UNICODE_ICON_NEGATIVE = u"\U0001F174"
EXPLICIT_UNICODE_ICON_STANDARD = u"\U0001F134"

ITEM_RESPONSE_TTL_SECONDS = 600  # 600s
ITEM_RESPONSE_CACHE = {}


MEDIA_TYPES_MENU_MAPPING = {
    ROOT_MEDIA_CONTENT_TYPE: {
        "title": {
            "en": "Media Library",
            "ru": "Библиотека",
        },
        "sort_children": False,
        "children_media_class": MEDIA_CLASS_DIRECTORY,
        "menu_group": [
            "current_user_playlists",
            "current_user_personal_mixes",
            "current_user_yandex_mixes",
            "current_user_likes",
            "genres",
            # "popular_artists",
            # "popular_tracks",
            "new_releases",
            "new_playlists",
        ]
    },
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
    "current_user_yandex_mixes": {
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
        "menu_group": [
            lambda c, l: generate_browse_media_object(
                c.users_playlists(kind='3'),
                payload={
                    'title': 'Моя коллекция' if l == 'ru' else 'Favourites',
                    'thumbnail': "/blocks/playlist-cover/playlist-cover_like_2x.png",
                }
            ),
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
            "ru": "Музыкальные жанры",
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


def process_thumbnail(thumbnail: str):
    if '%%' in thumbnail:
        thumbnail = thumbnail.replace('%%', '200x200')
    if thumbnail.startswith('/'):
        thumbnail = 'https://music.yandex.ru' + thumbnail
    elif not thumbnail.startswith(('http://', 'https://')):
        thumbnail = 'https://' + thumbnail
    return thumbnail


def generate_browse_media_object(
        media_object: MediaObjectType,
        payload: Optional[dict] = None,
        with_children: bool = False,
        sort_children: bool = True,
        timeout: Union[float, int] = DEFAULT_REQUEST_TIMEOUT,
        language: str = DEFAULT_TITLE_LANGUAGE,
) -> Optional[BrowseMedia]:
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
            media_object = media_object.with_tracks(timeout=timeout)
            if media_object.volumes:
                for volume in media_object.volumes:
                    volume_tracks = generate_browse_media_objects_from_list(
                        volume,
                        with_children=False,
                        sort_children=sort_children,
                        timeout=timeout,
                        language=language
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
            artist_albums = media_object.get_albums(timeout=timeout)
            params["children"] = generate_browse_media_objects_from_list(
                artist_albums,
                with_children=False,
                sort_children=sort_children,
                timeout=timeout,
                language=language,
            )

    elif isinstance(media_object, Playlist):
        params.update({
            "title": media_object.title,
            "media_content_type": MEDIA_TYPE_PLAYLIST,
            "media_class": MEDIA_CLASS_PLAYLIST,
            "thumbnail": media_object.cover.uri,
            "media_content_id": f'{media_object.owner.uid}:{media_object.kind}',
            "can_play": True,
            "can_expand": True,
        })
        if with_children:
            playlist_tracks = media_object.fetch_tracks(timeout=timeout)
            params["children"] = generate_browse_media_objects_from_list(
                playlist_tracks,
                with_children=False,
                sort_children=sort_children,
                timeout=timeout,
                language=language
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
            mix_link_playlists = media_object.client.tags(mix_link_tag, timeout=timeout)
            params["children"] = []
            if mix_link_playlists and mix_link_playlists.ids:
                playlists = get_playlists_from_ids(media_object.client, mix_link_playlists.ids)
                if playlists:
                    params["children"] = generate_browse_media_objects_from_list(
                        playlists,
                        with_children=False,
                        sort_children=False,
                        timeout=timeout,
                        language=language
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
            playlists = get_playlists_from_ids(media_object.client, media_object.ids, timeout=timeout)
            params["children"] = generate_browse_media_objects_from_list(
                playlists,
                with_children=False,
                sort_children=False,
                timeout=timeout,
                language=language
            )

    elif isinstance(media_object, Genre):
        if media_object.titles and language in media_object.titles:
            title = media_object.titles[language]['title']
        else:
            title = media_object.title

        if media_object.radio_icon:
            params["thumbnail"] = media_object.radio_icon.image_url
        elif media_object.images:
            params["thumbnail"] = getattr(media_object.images, '_300x300', None)

        params.update({
            "title": title,
            "media_content_type": MEDIA_TYPE_GENRE,
            "media_content_id": media_object.id,
            "media_class": MEDIA_CLASS_DIRECTORY,
            "can_play": False,
            "can_expand": True,
        })

        if with_children:
            children = []
            if media_object.sub_genres:
                children.extend(generate_browse_media_objects_from_list(
                    filter(lambda x: x.show_in_menu, media_object.sub_genres),
                    with_children=False,
                    sort_children=False,
                    timeout=timeout,
                    language=language
                ))

            genre_playlists = media_object.client.tags(media_object.id, timeout=timeout)
            if genre_playlists and genre_playlists.ids:
                playlists = get_playlists_from_ids(media_object.client, genre_playlists.ids)
                if playlists:
                    children.extend(generate_browse_media_objects_from_list(
                        playlists,
                        with_children=False,
                        sort_children=False,
                        timeout=timeout,
                        language=language
                    ))

            params["children"] = children

    else:
        return None

    if payload:
        params.update(payload)

    if params.get("thumbnail") is not None:
        params["thumbnail"] = process_thumbnail(params["thumbnail"])

    return BrowseMedia(**params)


def generate_browse_media_objects_from_list(
        source_list: Iterable[MediaObjectType],
        with_children: bool = False,
        sort_children: bool = True,
        timeout: Union[float, int] = DEFAULT_REQUEST_TIMEOUT,
        language: str = DEFAULT_TITLE_LANGUAGE,
) -> List[BrowseMedia]:
    generated_objects = []
    for media_object in source_list:
        generated_object = generate_browse_media_object(
            media_object,
            with_children=with_children,
            sort_children=sort_children,
            timeout=timeout,
            language=language,
        )
        if generated_object is None:
            continue

        generated_objects.append(generated_object)

    if sort_children:
        return sorted(generated_objects, key=lambda x: x.title)
    return generated_objects


def get_playlists_from_ids(
        music_client: Client,
        playlist_ids: List[Union[Dict[str, Union[int, str]], PlaylistId]],
        *args, **kwargs
):
    # noinspection PyUnresolvedReferences
    playlist_ids = [
        playlist if isinstance(playlist_ids, str) else f'{playlist["uid"]}:{playlist["kind"]}'
        for playlist in playlist_ids
    ]
    return music_client.playlists_list(playlist_ids=playlist_ids, *args, **kwargs)


def get_translated_title(config: dict, language: str = DEFAULT_TITLE_LANGUAGE) -> Optional[str]:
    if "title" not in config:
        return None
    return config["title"].get(language, config["title"][DEFAULT_TITLE_LANGUAGE])


def generate_menu_entry_from_config(
        music_client: Client,
        media_content_id: str,
        media_content_type: str,
        config: dict,
        language: str = DEFAULT_TITLE_LANGUAGE,
        with_children: bool = True,
):
    children = None
    if with_children and 'menu_group' in config:
        children = []
        for sub_media_content_type in config['menu_group']:
            if isinstance(sub_media_content_type, tuple):
                children.append(build_item_response(
                    music_client=music_client,
                    payload=dict(zip(("media_content_type", "media_content_id"), sub_media_content_type)),
                    with_children=False,
                ))

            elif callable(sub_media_content_type):
                result = sub_media_content_type(music_client, language)
                if result:
                    children.append(result)

            else:
                config = MEDIA_TYPES_MENU_MAPPING.get(sub_media_content_type)
                if not config:
                    _LOGGER.debug('Invalid submenu "%s" for menu "%s"', sub_media_content_type, media_content_type)
                    continue

                children.append(generate_menu_entry_from_config(
                    music_client=music_client,
                    media_content_id=sub_media_content_type,
                    media_content_type=sub_media_content_type,
                    config=config,
                    language=language,
                    with_children=False,
                ))

    return BrowseMedia(
        title=get_translated_title(config, language),
        media_class=config.get("media_class", MEDIA_CLASS_DIRECTORY),
        media_content_type=media_content_id,
        media_content_id=media_content_type,
        can_expand=True,
        can_play=False,
        children_media_class=config.get("children_media_class"),
        children=children,
        thumbnail=process_thumbnail(config["thumbnail"]) if config.get("thumbnail") else None,
    )


def recursive_genre_search(genre_id: str, genres: List[Genre]) -> Optional[Genre]:
    for genre in genres:
        if genre.id == genre_id:
            return genre
        if genre.sub_genres:
            sub_genre = recursive_genre_search(genre_id, genre.sub_genres)
            if sub_genre:
                return sub_genre


def build_item_response(
        music_client: Client,
        payload: dict,
        language: str = DEFAULT_TITLE_LANGUAGE,
        with_children: bool = True,
        sort_children: Optional[bool] = None,
        timeout: Union[int, float] = DEFAULT_REQUEST_TIMEOUT,
) -> BrowseMedia:
    media_content_type = payload["media_content_type"]
    media_content_id = payload["media_content_id"]
    config = MEDIA_TYPES_MENU_MAPPING.get(media_content_type, {})

    _LOGGER.debug('Building response: %s / %s', media_content_type, media_content_id)

    # Garbage collection
    now = time()
    for cache_key in list(ITEM_RESPONSE_CACHE.keys()):
        if (now - ITEM_RESPONSE_CACHE[cache_key][0]) > ITEM_RESPONSE_TTL_SECONDS:
            del ITEM_RESPONSE_CACHE[cache_key]

    # Check if cache has entry for current request
    cache_key = (media_content_type, media_content_id)
    if cache_key in ITEM_RESPONSE_CACHE:
        return ITEM_RESPONSE_CACHE[cache_key][1]

    try:
        media = None
        if media_content_type == MEDIA_TYPE_ALBUM:
            albums = music_client.albums(album_ids=media_content_id, timeout=timeout)
            if albums:
                media = albums[0]

        elif media_content_type == MEDIA_TYPE_ARTIST:
            artists = music_client.artists(artist_ids=media_content_id, timeout=timeout)
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

            media = music_client.users_playlists(user_id=user_id, kind=kind, timeout=timeout)

        elif media_content_type == MEDIA_TYPE_TRACK:
            media = music_client.tracks(track_ids=media_content_id, timeout=timeout)

        elif media_content_type == MEDIA_TYPE_MIX_TAG:
            media = music_client.tags(tag_id=media_content_id)

        elif media_content_type == MEDIA_TYPE_GENRE:
            genres = music_client.genres()
            media = recursive_genre_search(media_content_id, genres)

        else:
            items = None

            if media_content_type == "current_user_playlists":
                items = music_client.users_playlists_list(timeout=timeout)

            elif media_content_type == "current_user_personal_mixes":
                landing_root = music_client.landing('personalplaylists')
                if landing_root and len(landing_root.blocks) > 0:
                    blocks_entities = landing_root.blocks[0].entities
                    if blocks_entities:
                        items = [x.data.data for x in blocks_entities]

            elif media_content_type == "current_user_liked_playlists":
                likes = music_client.users_likes_playlists(timeout=timeout)
                if likes:
                    items = [x.playlist for x in likes]

            elif media_content_type == "current_user_liked_artists":
                likes = music_client.users_likes_artists(timeout=timeout)
                if likes:
                    items = [x.artist for x in likes]

            elif media_content_type == "current_user_liked_albums":
                likes = music_client.users_likes_albums(timeout=timeout)
                if likes:
                    items = [x.album for x in likes]

            elif media_content_type == "current_user_liked_tracks":
                track_list = music_client.users_likes_tracks(timeout=timeout)
                if track_list:
                    # @TODO: this method doesn't support timeout, yet...
                    items = track_list.fetch_tracks()

            elif media_content_type == "new_releases":
                landing_list = music_client.new_releases(timeout=timeout)
                if landing_list:
                    album_ids = landing_list.new_releases
                    if album_ids:
                        items = music_client.albums(album_ids=album_ids, timeout=timeout)

            elif media_content_type == "new_playlists":
                landing_list = music_client.new_playlists(timeout=timeout)
                if landing_list:
                    playlist_ids = landing_list.new_playlists
                    if playlist_ids:
                        # noinspection PyTypeChecker
                        items = get_playlists_from_ids(music_client, playlist_ids, timeout=timeout)

            elif media_content_type == "current_user_yandex_mixes":
                landing_root = music_client.landing('mixes')
                if landing_root and len(landing_root.blocks) > 0:
                    blocks_entities = landing_root.blocks[0].entities
                    if blocks_entities:
                        items = [x.data for x in blocks_entities]

            elif media_content_type == "popular_artists":
                pass

            elif media_content_type == "popular_tracks":
                pass

            elif media_content_type == "genres":
                items = music_client.genres(timeout=timeout)
                remove_genre_id = None
                for i, genre in enumerate(items):
                    if genre.id == 'all':
                        remove_genre_id = i
                        break

                if remove_genre_id is not None:
                    items.pop(remove_genre_id)

            elif media_content_type in MEDIA_TYPES_MENU_MAPPING:
                return generate_menu_entry_from_config(
                    music_client=music_client,
                    media_content_id=media_content_id,
                    media_content_type=media_content_type,
                    config=MEDIA_TYPES_MENU_MAPPING[media_content_type],
                    language=language,
                    with_children=with_children,
                )

            else:
                _LOGGER.debug('Unknown media type')
                raise UnknownMediaType

            if with_children:
                if sort_children is None:
                    sort_children = config.get("sort_children", DEFAULT_SORT_CHILDREN)

                children = generate_browse_media_objects_from_list(
                    items,
                    with_children=False,
                    sort_children=sort_children,
                    timeout=timeout
                ) if items else None
            else:
                children = None

            browse_media_object = BrowseMedia(
                title=get_translated_title(config, language),
                media_class=config.get("media_class", MEDIA_CLASS_DIRECTORY),
                media_content_id=media_content_id,
                media_content_type=media_content_type,
                can_play=False,
                can_expand=True,
                children_media_class=config.get("children_media_class"),
                children=children,
            )

            ITEM_RESPONSE_CACHE[cache_key] = (time(), browse_media_object)

            return browse_media_object

        if media is None:
            _LOGGER.debug('Unknown media: %s(%s)', media_content_type, media_content_id)
            raise UnknownMediaType

        browse_media_object = generate_browse_media_object(
            media,
            with_children=with_children,
            sort_children=False,
            language=language
        )

        ITEM_RESPONSE_CACHE[cache_key] = (time(), browse_media_object)

        return browse_media_object

    except TimedOut:
        raise TimeoutDataFetching(f'Timed out while fetching {media_content_type} / {media_content_id}') from None

    except Exception:
        if cache_key in ITEM_RESPONSE_CACHE:
            del ITEM_RESPONSE_CACHE[cache_key]
        raise
