from ..utils import VotiyException


class VotifyUrlParseException(VotiyException):
    def __init__(self, url: str):
        super().__init__(f"Failed to parse Spotify URL: {url}")

        self.url = url


class VotifyUnsupportedMediaTypeException(VotiyException):
    def __init__(self, media_type: str):
        super().__init__(f"Unsupported URL media type: {media_type}")

        self.media_type = media_type


class VotifyDrmDisabledException(VotiyException):
    def __init__(self, media_id: str, media_metadata: dict | None = None):
        super().__init__(f"DRM is disabled, cannot process media: {media_id}")

        self.media_id = media_id
        self.media_metadata = media_metadata


class VotifyMediaNotFoundException(VotiyException):
    def __init__(self, media_id: str, media_metadata: dict | None = None):
        super().__init__(f"Media not found: {media_id}")

        self.media_id = media_id
        self.media_metadata = media_metadata


class VotifyMediaUnstreamableException(VotiyException):
    def __init__(self, media_id: str, media_metadata: dict | None = None):
        super().__init__(f"Media is not streamable: {media_id}")

        self.media_id = media_id
        self.media_metadata = media_metadata


class VotifyMediaAudioQualityNotAvailableException(VotiyException):
    def __init__(self, media_id: str, playback_info: dict | None = None):
        super().__init__(f"Selected audio quality is not available: {media_id}")

        self.media_id = media_id
        self.playback_info = playback_info
