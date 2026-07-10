import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from spotipy.exceptions import SpotifyException

from app.main import (
    app,
    CounterService,
    get_service,
    spotify_debug_info,
    spotify_play_track,
    spotify_playlist_tracks,
)


def build_service(tmp_path: Path) -> CounterService:
    return CounterService(tmp_path / "counter.db")


def test_counter_persists_across_service_instances(tmp_path: Path) -> None:
    first_service = build_service(tmp_path)
    assert first_service.get_counter() == 0

    first_service.increment(5)
    first_service.decrement(2)
    first_service.set_counter(11)

    second_service = build_service(tmp_path)
    assert second_service.get_counter() == 11


def test_api_increment_decrement_and_set(tmp_path: Path) -> None:
    test_db = tmp_path / "counter.db"
    test_service = CounterService(test_db)
    app.dependency_overrides[get_service] = lambda: test_service

    try:
        client = TestClient(app)

        assert client.get("/", follow_redirects=False).status_code == 307
        assert client.get("/tv").status_code == 200
        assert client.get("/admin").status_code == 200

        assert client.get("/api/counter").json() == {"value": 0}

        response = client.post("/api/counter/increment", json={"amount": 3})
        assert response.status_code == 200
        assert response.json() == {"value": 3}

        response = client.post("/api/counter/decrement", json={"amount": 2})
        assert response.status_code == 200
        assert response.json() == {"value": 1}

        response = client.post("/api/counter/set", json={"value": 8})
        assert response.status_code == 200
        assert response.json() == {"value": 8}

        response = client.post("/api/counter/increment", json={"amount": 0})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_spotify_playlist_tracks_returns_error_payload(monkeypatch) -> None:
    class FakeSpotify:
        def playlist_items(self, *_args, **_kwargs):
            raise SpotifyException(403, -1, "scope missing")

        def current_user_playlists(self, limit=20):
            return {"items": []}

    monkeypatch.setattr("app.main.get_spotify", lambda: FakeSpotify())

    response = spotify_playlist_tracks()

    assert response.status_code == 502
    assert response.body


def test_spotify_playlist_tracks_falls_back_to_user_playlist(monkeypatch) -> None:
    class FakeSpotify:
        def __init__(self) -> None:
            self.calls = []

        def playlist_items(self, playlist_id, *_args, **_kwargs):
            self.calls.append(playlist_id)
            if playlist_id == "4nvPDDQYaDf794lrabDuAv":
                raise SpotifyException(404, -1, "not found")
            return {
                "items": [
                    {
                        "track": {
                            "name": "Fallback song",
                            "uri": "spotify:track:1",
                            "artists": [{"name": "Fallback Artist"}],
                            "album": {"name": "Fallback Album"},
                            "duration_ms": 180000,
                        }
                    }
                ]
            }

        def current_user_playlists(self, limit=20):
            return {"items": [{"id": "fallback-id", "name": "Fallback Playlist"}]}

    fake_spotify = FakeSpotify()
    monkeypatch.setattr("app.main.get_spotify", lambda: fake_spotify)

    response = spotify_playlist_tracks()

    assert response["playlist_id"] == "fallback-id"
    assert response["tracks"][0]["name"] == "Fallback song"


def test_spotify_playlist_tracks_parses_item_wrapped_tracks(monkeypatch) -> None:
    class FakeSpotify:
        def playlist_items(self, *_args, **_kwargs):
            return {
                "items": [
                    {
                        "item": {
                            "name": "Wrapped song",
                            "uri": "spotify:track:2",
                            "artists": [{"name": "Wrapped Artist"}],
                            "album": {"name": "Wrapped Album"},
                            "duration_ms": 200000,
                        }
                    }
                ]
            }

        def current_user_playlists(self, limit=20):
            return {"items": []}

    monkeypatch.setattr("app.main.get_spotify", lambda: FakeSpotify())

    response = spotify_playlist_tracks()

    assert response["tracks"][0]["name"] == "Wrapped song"
    assert response["tracks"][0]["artists"] == ["Wrapped Artist"]


def test_spotify_play_track_uses_playlist_context_and_shuffle(monkeypatch) -> None:
    class FakeSpotify:
        def __init__(self) -> None:
            self.calls = []

        def start_playback(self, **kwargs) -> None:
            self.calls.append(("start_playback", kwargs))

        def shuffle(self, state: bool) -> None:
            self.calls.append(("shuffle", state))

    fake_spotify = FakeSpotify()
    monkeypatch.setattr("app.main.get_spotify", lambda: fake_spotify)

    response = spotify_play_track(SimpleNamespace(uri="spotify:track:123"))

    assert response == {"ok": True}
    assert fake_spotify.calls[0][0] == "start_playback"
    assert fake_spotify.calls[0][1]["context_uri"] == "spotify:playlist:4nvPDDQYaDf794lrabDuAv"
    assert fake_spotify.calls[0][1]["offset"] == {"uri": "spotify:track:123"}
    assert fake_spotify.calls[1] == ("shuffle", True)


def test_spotify_debug_info_reports_scopes(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main._get_spotify_token_info",
        lambda: {"access_token": "abc", "scope": "playlist-read-private user-read-email"},
    )

    response = spotify_debug_info()

    assert response["token_present"] is True
    assert "playlist-read-private" in response["scopes"]
