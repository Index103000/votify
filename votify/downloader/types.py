from dataclasses import dataclass
import uuid

from ..interface.types import SpotifyMedia


@dataclass
class DownloadItem:
    media: SpotifyMedia
    uuid_: str = uuid.uuid4().hex[:8]
    staged_path: str = None
    final_path: str = None
    playlist_file_path: str = None
    synced_lyrics_path: str = None
    cover_path: str = None
