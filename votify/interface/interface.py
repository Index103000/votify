import logging
from typing import AsyncGenerator

from .audio import SpotifyAudioInterface
from .episode import SpotifyEpisodeInterface
from .episode_video import SpotifyEpisodeVideoInterface
from .exceptions import (
    VotifyDrmDisabledException,
    VotifyMediaNotFoundException,
    VotifyMediaUnstreamableException,
    VotifyUnsupportedMediaTypeException,
)
from .music_video import SpotifyMusicVideoInterface
from .song import SpotifySongInterface
from .types import SpotifyMedia

logger = logging.getLogger(__name__)


class SpotifyInterface:
    def __init__(
        self,
        base: SpotifyAudioInterface,
        song: SpotifySongInterface,
        episode: SpotifyEpisodeInterface,
        music_video: SpotifyMusicVideoInterface,
        episode_video: SpotifyEpisodeVideoInterface,
    ) -> None:
        self.base = base
        self.song = song
        self.episode = episode
        self.music_video = music_video
        self.episode_video = episode_video

    async def _get_track_media(
        self,
        track_id: str,
        track_data: dict | None = None,
        album_data: dict | None = None,
        album_items: list[dict] | None = None,
    ) -> SpotifyMedia | None:
        if self.base.no_drm:
            raise VotifyDrmDisabledException(track_id)

        if not track_data:
            track_response = await self.base.api.get_track(track_id)
            track_data = track_response["data"]["trackUnion"]

        if track_data["__typename"] != "Track":
            raise VotifyMediaNotFoundException(track_id, track_data)

        if not track_data["playability"]["playable"]:
            raise VotifyMediaUnstreamableException(track_id, track_data)

        playback_info = await self.base.get_playback_info(
            media_id=track_id,
            media_type="track",
        )
        assert playback_info, "Playback info should be available for playable track"

        if self.base.is_video(playback_info):
            return await self.music_video.proccess_media(
                playback_info=playback_info,
                **(
                    {
                        "track_data": track_data,
                        "album_data": album_data,
                    }
                    if playback_info["metadata"]["uri"] == track_data["uri"]
                    else {}
                ),
            )

        return await self.song.proccess_media(
            playback_info=playback_info,
            track_data=track_data,
            album_data=album_data,
            album_items=album_items,
        )

    async def _get_episode_media(
        self,
        episode_id: str,
        episode_data: dict | None = None,
        show_data: dict | None = None,
        show_items: list[dict] | None = None,
    ) -> SpotifyMedia | None:
        if not episode_data:
            episode_response = await self.base.api.get_episode(episode_id)
            episode_data = episode_response["data"]["episodeUnionV2"]

        if episode_data["__typename"] != "Episode":
            raise VotifyMediaNotFoundException(episode_id, episode_data)

        if not episode_data["playability"]["playable"]:
            raise VotifyMediaUnstreamableException(episode_id, episode_data)

        playback_info = await self.base.get_playback_info(
            media_id=episode_id,
            media_type="episode",
        )
        assert playback_info, "Playback info should be available for playable episode"

        if self.base.is_video(playback_info):
            return await self.episode_video.proccess_media(
                playback_info=playback_info,
                episode_data=episode_data,
                show_data=show_data,
                show_items=show_items,
            )

        return await self.episode.proccess_media(
            playback_info=playback_info,
            episode_data=episode_data,
            show_data=show_data,
            show_items=show_items,
        )

    async def _get_album_media(
        self,
        media_id: str,
    ) -> AsyncGenerator[SpotifyMedia, None]:
        if self.base.no_drm:
            raise VotifyDrmDisabledException(media_id)

        album_data, album_items = await self.base.get_album_data_cached(
            album_id=media_id
        )

        if album_data["__typename"] != "Album":
            raise VotifyMediaNotFoundException(media_id, album_data)
        else:
            for item in album_items:
                track_data = item["track"]
                track_id = track_data["uri"].split(":")[-1]

                yield await self._get_track_media(
                    track_id=track_id,
                    track_data=track_data,
                    album_data=album_data,
                    album_items=album_items,
                )

    async def _get_show_media(
        self,
        media_id: str,
    ) -> AsyncGenerator[SpotifyMedia, None]:
        show_data, show_items = await self.base.get_show_data_cached(show_id=media_id)

        if show_data["__typename"] != "Podcast":
            raise VotifyMediaNotFoundException(media_id, show_data)
        else:
            for item in show_items:
                episode_data = item["entity"]["data"]
                episode_id = item["entity"]["_uri"].split(":")[-1]

                yield await self._get_episode_media(
                    episode_id=episode_id,
                    episode_data=episode_data,
                    show_data=show_data,
                    show_items=show_items,
                )

    async def _get_playlist_media(
        self,
        media_id: str,
    ) -> AsyncGenerator[SpotifyMedia, None]:
        playlist_response = await self.base.api.get_playlist(media_id)
        playlist_data = playlist_response["data"]["playlistV2"]

        if playlist_data["__typename"] != "Playlist":
            raise VotifyMediaNotFoundException(media_id, playlist_data)
        else:
            playlist_items = playlist_data["content"]["items"]
            while len(playlist_items) < playlist_data["content"]["totalCount"]:
                playlist_response = await self.base.api.get_playlist(
                    media_id,
                    len(playlist_items),
                )
                playlist_items.extend(
                    playlist_response["data"]["playlistV2"]["content"]["items"]
                )

            for index, item in enumerate(playlist_items):
                track_data = item["itemV2"]["data"]
                track_id = track_data["uri"].split(":")[-1]

                if track_data["__typename"] == "Track":
                    media = await self._get_track_media(
                        track_id=track_id,
                        track_data=track_data,
                    )
                elif track_data["__typename"] == "Episode":
                    media = await self._get_episode_media(
                        episode_id=track_id,
                        episode_data=track_data,
                    )
                else:
                    raise VotifyMediaNotFoundException(track_id, track_data)

                media.playlist_metadata = playlist_data
                media.playlist_tags = self.base.get_playlist_tags(playlist_data, index)

    async def get_media_by_url(self, url: str) -> AsyncGenerator[SpotifyMedia, None]:
        url_info = self.base.parse_url_info(url)

        if url_info.media_type in self.base.disallowed_media_types:
            raise VotifyUnsupportedMediaTypeException(url_info.media_type)
        elif url_info.media_type == "track":
            yield await self._get_track_media(url_info.media_id)
        elif url_info.media_type == "episode":
            yield await self._get_episode_media(url_info.media_id)
        elif url_info.media_type == "album":
            async for media in self._get_album_media(url_info.media_id):
                yield media
        elif url_info.media_type == "show":
            async for media in self._get_show_media(url_info.media_id):
                yield media
        elif url_info.media_type == "playlist":
            async for media in self._get_playlist_media(url_info.media_id):
                yield media
