from __future__ import annotations

import time
from secrets import compare_digest, token_urlsafe

from fastapi import HTTPException
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

from .config import Settings


class SpotifyService:
    """Spotify OAuth client with a single in-memory administrator session."""

    scope = (
        "streaming user-read-email user-read-private user-modify-playback-state "
        "user-read-playback-state playlist-read-private playlist-read-collaborative"
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._token_info: dict | None = None
        self._oauth_state: str | None = None
        self._oauth: SpotifyOAuth | None = None

    @property
    def oauth(self) -> SpotifyOAuth:
        if not self.is_configured:
            raise HTTPException(503, "Spotify no está configurado.")
        if self._oauth is None:
            self._oauth = SpotifyOAuth(
                client_id=self.settings.spotify_client_id,
                client_secret=self.settings.spotify_client_secret,
                redirect_uri=self.settings.spotify_redirect_uri,
                scope=self.scope,
            )
        return self._oauth

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.spotify_client_id and self.settings.spotify_client_secret)

    def authorize_url(self) -> str:
        if not self.is_configured:
            raise HTTPException(503, "Spotify no está configurado.")
        self._oauth_state = token_urlsafe(32)
        return self.oauth.get_authorize_url(state=self._oauth_state)

    def exchange_code(self, code: str, state: str) -> None:
        if not self.is_configured:
            raise HTTPException(503, "Spotify no está configurado.")
        if not self._oauth_state or not compare_digest(state, self._oauth_state):
            raise HTTPException(400, "La respuesta de autorización de Spotify no es válida.")
        self._oauth_state = None
        self._token_info = self.oauth.get_access_token(code)

    def has_token(self) -> bool:
        return self._token_info is not None

    def debug_info(self) -> dict:
        token_info = self._token_info or {}
        scope = token_info.get("scope", "")
        return {
            "configured": self.is_configured,
            "token_present": bool(token_info),
            "scope": scope,
            "scopes": [item for item in scope.split(" ") if item],
            "playlist_id": self.settings.spotify_default_playlist,
        }

    def client(self) -> Spotify:
        if not self.is_configured:
            raise HTTPException(503, "Spotify no está configurado.")
        if not self._token_info:
            raise HTTPException(401, "Spotify no está autenticado.")
        if self._token_info["expires_at"] - time.time() < 300:
            self._token_info = self.oauth.refresh_access_token(
                self._token_info["refresh_token"]
            )
        return Spotify(auth=self._token_info["access_token"])

    def access_token(self) -> str:
        self.client()
        assert self._token_info is not None
        return self._token_info["access_token"]
