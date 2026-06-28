from __future__ import annotations

import sys, os
from pathlib import Path
import time

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.schemas import CounterChangeRequest, CounterResponse, CounterSetRequest
from app.service import CounterService

from fastapi.responses import RedirectResponse
from starlette.requests import Request
from spotipy.oauth2 import SpotifyOAuth
from spotipy import Spotify

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "counter.db"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

spotify_tokens = {}

app = FastAPI(title="DrinkCounter")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
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
        "user-read-playback-state"
    )
)


def get_service() -> CounterService:
    return service


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/tv", status_code=307)


@app.get("/tv", response_class=HTMLResponse)
def tv(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="tv.html", context={})


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="admin.html", context={})


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

    token_info = (sp_oauth.get_access_token(code))

    spotify_tokens["token"] = (token_info)

    return RedirectResponse("/tv")


@app.get("/token")
def token():

    token_info = spotify_tokens.get("token")

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

        spotify_tokens["token"] = token_info

    return {
        "access_token":
        token_info["access_token"]
    }


@app.get("/has-token")
def has_token():
    return {"ok": "token" in spotify_tokens}


import time
from spotipy import Spotify


def get_spotify():

    if "token" not in spotify_tokens:

        raise HTTPException(401, "Spotify non autenticado")

    token_info = (spotify_tokens["token"])

    if (token_info["expires_at"] - time.time() < 300):
        token_info = (sp_oauth.refresh_access_token(token_info["refresh_token"]))

        spotify_tokens["token"] = token_info

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
