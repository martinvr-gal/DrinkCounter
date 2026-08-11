from __future__ import annotations

import json
import time
from secrets import compare_digest, token_urlsafe

from fastapi import HTTPException
from spotipy import Spotify
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

from .config import Settings


class SpotifyService:
    """Spotify OAuth client with a user session, optionally bootstrapped from env."""

    scope = (
        "streaming user-read-email user-read-private user-modify-playback-state "
        "user-read-playback-state playlist-read-private playlist-read-collaborative"
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # A refresh token is a long-lived credential obtained during a previous
        # user authorization. It lets a deployed instance recover its Spotify
        # session after restarts without redirecting an administrator to Spotify.
        self._token_info: dict | None = self._load_token()
        self._oauth_state: str | None = None
        self._oauth: SpotifyOAuth | None = None

    def _load_token(self) -> dict | None:
        if self.settings.spotify_refresh_token:
            return {"refresh_token": self.settings.spotify_refresh_token}
        try:
            token = json.loads(self.settings.spotify_token_path.read_text())
            return token if isinstance(token, dict) and token.get("refresh_token") else None
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None

    def _save_token(self) -> None:
        if not self._token_info or not self._token_info.get("refresh_token"):
            return
        path = self.settings.spotify_token_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._token_info))
        path.chmod(0o600)

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
        self._save_token()

    def start_default_playlist(self) -> bool:
        """Start the configured playlist on the account's active Spotify device."""
        if not self.settings.spotify_autoplay or not self.settings.spotify_default_playlist:
            return False
        client = self.client()
        client.start_playback(
            context_uri=f"spotify:playlist:{self.settings.spotify_default_playlist}"
        )
        try:
            client.shuffle(True)
        except SpotifyException:
            # Playback works on devices that do not support changing shuffle.
            pass
        return True

    def pause_for_clip(self) -> bool:
        """Pause playback for a TV clip and report whether it was playing."""
        try:
            playback = self.client().current_playback()
            was_playing = bool(playback and playback.get("is_playing"))
            if was_playing:
                self.client().pause_playback()
            return was_playing
        except SpotifyException as exc:
            if exc.http_status == 404:
                return False
            raise

    def resume_after_clip(self, should_resume: bool) -> bool:
        """Resume only if this clip interrupted an active playback session."""
        if not should_resume:
            return False
        try:
            self.client().start_playback()
            return True
        except SpotifyException as exc:
            if exc.http_status == 404:
                return False
            raise

    def playlist_pages(self, playlist_id: str) -> list[dict]:
        """Fetch playlist items through Spotify's current /items endpoint."""
        client = self.client()
        page = client._get(
            f"playlists/{playlist_id}/items",
            limit=100,
            offset=0,
            additional_types="track",
        )
        pages = [page]
        while page.get("next"):
            page = client.next(page)
            pages.append(page)
        return pages

    def has_token(self) -> bool:
        return bool(self._token_info and self._token_info.get("refresh_token"))

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
        expires_at = self._token_info.get("expires_at", 0)
        if expires_at - time.time() < 300:
            refresh_token = self._token_info["refresh_token"]
            refreshed = self.oauth.refresh_access_token(refresh_token)
            # Spotify may omit refresh_token in a refresh response. Keep the
            # original one so subsequent renewals continue to work.
            refreshed.setdefault("refresh_token", refresh_token)
            self._token_info = refreshed
            self._save_token()
        return Spotify(auth=self._token_info["access_token"])

    def access_token(self) -> str:
        self.client()
        assert self._token_info is not None
        return self._token_info["access_token"]
