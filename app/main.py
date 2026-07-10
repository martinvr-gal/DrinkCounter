from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.schemas import (
    CounterChangeRequest,
    CounterResponse,
    CounterSetRequest,
    PlayTrackRequest,
)
from app.service import CounterService
from app.spotify_config import SPOTIFY_DEFAULT_PLAYLIST
from spotipy.oauth2 import SpotifyOAuth
from spotipy import Spotify
from spotipy.exceptions import SpotifyException

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "counter.db"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"
CLIPS_DIR = STATIC_DIR / "clips"

_spotify_tokens: dict = {}


def _get_spotify_token_info() -> dict | None:
    return _spotify_tokens.get("token")


def _set_spotify_token_info(token_info: dict) -> None:
    _spotify_tokens["token"] = token_info


app = FastAPI(title="DrinkCounter")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if CLIPS_DIR.exists() and CLIPS_DIR.is_dir():
    app.mount("/clips", StaticFiles(directory=str(CLIPS_DIR)), name="clips")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
service = CounterService(DB_PATH)

sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope=(
        "streaming "
        "user-read-email "
        "user-read-private "
        "user-modify-playback-state "
        "user-read-playback-state "
        "playlist-read-private "
        "playlist-read-collaborative"
    )
)


def get_service() -> CounterService:
    return service


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/tv", status_code=307)


@app.get("/tv", response_class=HTMLResponse)
def tv(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="tv.html",
        context={"spotify_playlist_id": SPOTIFY_DEFAULT_PLAYLIST},
    )


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"spotify_playlist_id": SPOTIFY_DEFAULT_PLAYLIST},
    )


@app.get("/api/counter", response_model=CounterResponse)
def read_counter(counter_service: CounterService = Depends(get_service)) -> CounterResponse:
    return CounterResponse(value=counter_service.get_counter())


@app.post("/api/counter/increment", response_model=CounterResponse)
def increment_counter(
    payload: CounterChangeRequest,
    counter_service: CounterService = Depends(get_service),
) -> CounterResponse:
    try:
        value = counter_service.increment(payload.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CounterResponse(value=value)


@app.post("/api/counter/decrement", response_model=CounterResponse)
def decrement_counter(
    payload: CounterChangeRequest,
    counter_service: CounterService = Depends(get_service),
) -> CounterResponse:
    try:
        value = counter_service.decrement(payload.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CounterResponse(value=value)


@app.post("/api/counter/set", response_model=CounterResponse)
def set_counter(
    payload: CounterSetRequest,
    counter_service: CounterService = Depends(get_service),
) -> CounterResponse:
    try:
        value = counter_service.set_counter(payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CounterResponse(value=value)


@app.get("/login")
def login():
    return RedirectResponse(
        url=sp_oauth.get_authorize_url()
    )


@app.get("/callback")
def callback(code: str):

    token_info = sp_oauth.get_access_token(code)

    _set_spotify_token_info(token_info)

    return RedirectResponse("/tv")


@app.get("/token")
def token():

    token_info = _get_spotify_token_info()

    if not token_info:
        raise HTTPException(
            status_code=401,
            detail="Spotify login required"
        )

    if token_info["expires_at"] - time.time() < 300:

        token_info = (
            sp_oauth.refresh_access_token(
                token_info["refresh_token"]
            )
        )

        _spotify_tokens["token"] = token_info

    return {
        "access_token":
        token_info["access_token"]
    }


@app.get("/has-token")
def has_token():
    return {"ok": _get_spotify_token_info() is not None}


def get_spotify():

    token_info = _get_spotify_token_info()

    if not token_info:
        raise HTTPException(401, "Spotify non autenticado")

    if token_info["expires_at"] - time.time() < 300:
        token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])

        _set_spotify_token_info(token_info)

    return Spotify(auth=token_info["access_token"])


@app.post("/api/spotify/play")
def spotify_play():

    sp = get_spotify()

    playback = sp.current_playback()

    if playback:
        if (playback["is_playing"]):
            sp.pause_playback()
        else:
            sp.start_playback()

    return {"ok": True}


@app.post("/api/spotify/next")
def spotify_next():

    get_spotify().next_track()

    return {"ok": True}


@app.post("/api/spotify/prev")
def spotify_prev():

    get_spotify().previous_track()

    return {"ok":True}


@app.get("/api/spotify/state")
def spotify_state():

    state = get_spotify().current_playback()

    return state


@app.get("/api/spotify/debug")
def spotify_debug_info():
    token_info = _get_spotify_token_info() or {}
    scopes = []
    if token_info.get("scope"):
        scopes = [scope.strip() for scope in token_info["scope"].split(" ") if scope.strip()]

    return {
        "token_present": bool(token_info),
        "scope": token_info.get("scope", ""),
        "scopes": scopes,
        "playlist_id": SPOTIFY_DEFAULT_PLAYLIST
    }


@app.get("/api/spotify/playlist-tracks")
def spotify_playlist_tracks():

    sp = get_spotify()
    playlist_id = SPOTIFY_DEFAULT_PLAYLIST

    playlist_array = []

    try:
        playlist = sp.playlist_items(
            playlist_id,
            limit=100,
            offset=0
        )
        
        while playlist.get("next"):
            playlist_array.append(playlist)
            playlist = sp.next(playlist)
    except SpotifyException:
        try:
            user_playlists = sp.current_user_playlists(limit=20)
            fallback_playlist = next(
                (
                    item.get("id")
                    for item in user_playlists.get("items", [])
                    if item.get("id")
                ),
                None,
            )
            if not fallback_playlist:
                raise SpotifyException(404, -1, "No playlists found")

            playlist_id = fallback_playlist
            playlist = sp.playlist_items(
                playlist_id,
                fields="items(track(name,uri,artists(name),album(name),duration_ms)),total",
                additional_types=["track"],
                limit=100,
                offset=0
            )
        
            playlist_array.append(playlist)
            while playlist.get("next"):
                playlist = sp.next(playlist)
        except SpotifyException as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "playlist_id": playlist_id,
                    "tracks": [],
                    "error": str(exc)
                }
            )
    
    tracks = []
    for playlist in playlist_array + [playlist]:
        for item in playlist.get("items", []):
            track = item.get("track") or item.get("item")
            if not track:
                continue
            tracks.append({
                "name": track.get("name"),
                "uri": track.get("uri"),
                "artists": [artist.get("name") for artist in track.get("artists", []) if artist.get("name")],
                "album": track.get("album", {}).get("name") if isinstance(track.get("album"), dict) else None,
                "duration_ms": track.get("duration_ms"),
            })

    return {
        "playlist_id": playlist_id,
        "tracks": tracks,
    }


@app.post("/api/spotify/play-track")
def spotify_play_track(payload: PlayTrackRequest):

    sp = get_spotify()
    sp.start_playback(
        context_uri=f"spotify:playlist:{SPOTIFY_DEFAULT_PLAYLIST}",
        offset={"uri": payload.uri},
    )
    try:
        sp.shuffle(True)
    except Exception:
        pass

    return {"ok": True}


@app.get("/api/clips")
def list_clips():

    if not CLIPS_DIR.exists() or not CLIPS_DIR.is_dir():
        return []

    clips = []
    for clip_path in sorted(CLIPS_DIR.iterdir()):
        if not clip_path.is_file():
            continue

        if clip_path.suffix.lower() not in {".mp4", ".webm", ".mov", ".m4v"}:
            continue

        clips.append(f"/clips/{quote(clip_path.name)}")

    return clips


@app.post("/api/spotify/pause")
def spotify_pause():

    get_spotify().pause_playback()

    return {"ok": True}


@app.post("/api/spotify/resume")
def spotify_resume():

    get_spotify().start_playback()

    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
