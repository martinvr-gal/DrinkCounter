import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from spotipy.exceptions import SpotifyException
from .auth import admin_required, create_token
from .config import get_settings
from .counter import CounterService
from .database import Base, engine, get_db
from .models import ImageStatus, Photo
from .schemas import CounterChangeRequest, CounterResponse, CounterSetRequest, LoginRequest, PlayTrackRequest, PhotoOut, PhotoPage, StatusChange, Token
from .spotify import SpotifyService
from .storage import LocalStorage
from .websocket import manager

logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}')
settings = get_settings(); storage = LocalStorage(settings.upload_folder); counter_service = CounterService(settings.counter_database_path); spotify_service = SpotifyService(settings)
app = FastAPI(title="Photo Gallery API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup() -> None: Base.metadata.create_all(bind=engine)

def image_url(photo: Photo) -> str: return f"/images/{photo.status.value.lower()}/{photo.stored_filename}"
def serialize(photo: Photo) -> PhotoOut:
    return PhotoOut(id=photo.id, user_name=photo.user_name, original_filename=photo.original_filename, status=photo.status, version=photo.version, uploaded_at=photo.uploaded_at, reviewed_at=photo.reviewed_at, url=image_url(photo))
def page_query(db: Session, image_status: ImageStatus | None, page: int, page_size: int, search: str | None, order: str) -> PhotoPage:
    where = [] if image_status is None else [Photo.status == image_status]
    if search: where.append(Photo.user_name.ilike(f"%{search.strip()}%"))
    direction = Photo.uploaded_at.asc() if order == "asc" else Photo.uploaded_at.desc()
    total = db.scalar(select(func.count()).select_from(Photo).where(*where)) or 0
    records = db.scalars(select(Photo).where(*where).order_by(direction).offset((page-1)*page_size).limit(page_size)).all()
    return PhotoPage(items=[serialize(p) for p in records], total=total, page=page, page_size=page_size)

@app.get("/health")
def health(): return {"status": "ok"}

@app.get("/api/counter", response_model=CounterResponse)
def read_counter() -> CounterResponse:
    return CounterResponse(value=counter_service.get_counter())

@app.post("/api/counter/increment", response_model=CounterResponse)
def increment_counter(payload: CounterChangeRequest, _=Depends(admin_required)) -> CounterResponse:
    return CounterResponse(value=counter_service.increment(payload.amount))

@app.post("/api/counter/decrement", response_model=CounterResponse)
def decrement_counter(payload: CounterChangeRequest, _=Depends(admin_required)) -> CounterResponse:
    return CounterResponse(value=counter_service.decrement(payload.amount))

@app.post("/api/counter/set", response_model=CounterResponse)
def set_counter(payload: CounterSetRequest, _=Depends(admin_required)) -> CounterResponse:
    return CounterResponse(value=counter_service.set_counter(payload.value))

@app.post("/upload", response_model=PhotoOut, status_code=status.HTTP_201_CREATED)
async def upload(user_name: str = Query(min_length=1, max_length=120), image: UploadFile = File(...), db: Session = Depends(get_db)):
    allowed = {"image/jpeg", "image/png", "image/webp", "image/heic"}
    if image.content_type not in allowed: raise HTTPException(415, "Formato no permitido. Usa JPG, PNG, WebP o HEIC.")
    contents = await image.read(settings.max_upload_bytes + 1)
    if len(contents) > settings.max_upload_bytes: raise HTTPException(413, "La imagen supera el tamaño máximo permitido.")
    await image.seek(0)
    stored, path = storage.save_pending(image)
    photo = Photo(user_name=user_name.strip(), original_filename=Path(image.filename or "image").name, stored_filename=stored, path=path, mime_type=image.content_type)
    db.add(photo); db.commit(); db.refresh(photo)
    return serialize(photo)

@app.post("/admin/login", response_model=Token)
def login(payload: LoginRequest):
    if payload.username != settings.admin_username or payload.password != settings.admin_password: raise HTTPException(401, "Credenciales incorrectas")
    return Token(access_token=create_token(payload.username))

@app.get("/admin/pending", response_model=PhotoPage)
def pending(page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100), _=Depends(admin_required), db: Session = Depends(get_db)):
    return page_query(db, ImageStatus.PENDING, page, page_size, None, "asc")

async def change_photo(photo_id: int, payload: StatusChange, db: Session, target: ImageStatus) -> PhotoOut:
    result = db.execute(update(Photo).where(Photo.id == photo_id, Photo.version == payload.version).values(status=target, version=Photo.version + 1, reviewed_at=datetime.utcnow()))
    if result.rowcount != 1:
        db.rollback(); raise HTTPException(409, "Esta imagen ya fue modificada por otro administrador.")
    photo = db.get(Photo, photo_id)
    assert photo is not None
    old_status = ImageStatus(photo.path.split("/", 1)[0].upper())
    photo.path = storage.move(photo.stored_filename, old_status, target)
    db.commit(); db.refresh(photo)
    response = serialize(photo)
    await manager.broadcast({"type": "photo.updated", "photo": response.model_dump(mode="json")})
    return response

@app.post("/admin/approve/{photo_id}", response_model=PhotoOut)
async def approve(photo_id: int, payload: StatusChange, db: Session = Depends(get_db), _=Depends(admin_required)): return await change_photo(photo_id, payload, db, ImageStatus.APPROVED)
@app.post("/admin/reject/{photo_id}", response_model=PhotoOut)
async def reject(photo_id: int, payload: StatusChange, db: Session = Depends(get_db), _=Depends(admin_required)): return await change_photo(photo_id, payload, db, ImageStatus.REJECTED)

@app.post("/admin/status/{photo_id}", response_model=PhotoOut)
async def set_status(photo_id: int, payload: StatusChange, db: Session = Depends(get_db), _=Depends(admin_required)):
    """Move a photo between any moderation folders while preserving its history."""
    return await change_photo(photo_id, payload, db, payload.status)

@app.get("/gallery/{gallery_status}", response_model=PhotoPage)
def gallery(gallery_status: str, page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100), search: str | None = None, order: str = Query("desc", pattern="^(asc|desc)$"), db: Session = Depends(get_db)):
    try: target = None if gallery_status == "all" else ImageStatus(gallery_status.upper())
    except ValueError: raise HTTPException(404, "Estado no válido")
    return page_query(db, target, page, page_size, search, order)

@app.get("/images/{folder}/{filename}")
def image_file(folder: str, filename: str):
    if folder not in {"pending", "approved", "rejected"} or Path(filename).name != filename: raise HTTPException(404)
    path = settings.upload_folder / folder / filename
    if not path.is_file(): raise HTTPException(404)
    return FileResponse(path)

@app.get("/admin/spotify/login")
def spotify_login(_=Depends(admin_required)):
    return RedirectResponse(spotify_service.authorize_url())

@app.get("/admin/spotify/callback")
def spotify_callback(code: str, state: str):
    spotify_service.exchange_code(code, state)
    return RedirectResponse("/admin")

@app.get("/api/spotify/has-token")
def spotify_has_token(_=Depends(admin_required)):
    return {"ok": spotify_service.has_token()}

@app.get("/api/spotify/debug")
def spotify_debug_info(_=Depends(admin_required)):
    return spotify_service.debug_info()

@app.get("/api/spotify/token")
def spotify_token(_=Depends(admin_required)):
    return {"access_token": spotify_service.access_token()}

@app.post("/api/spotify/play")
def spotify_play(_=Depends(admin_required)):
    client = spotify_service.client()
    playback = client.current_playback()
    if playback:
        if playback.get("is_playing"):
            client.pause_playback()
        else:
            client.start_playback()
    return {"ok": True}

@app.post("/api/spotify/pause")
def spotify_pause(_=Depends(admin_required)):
    spotify_service.client().pause_playback()
    return {"ok": True}

@app.post("/api/spotify/resume")
def spotify_resume(_=Depends(admin_required)):
    spotify_service.client().start_playback()
    return {"ok": True}

@app.post("/api/spotify/next")
def spotify_next(_=Depends(admin_required)):
    spotify_service.client().next_track()
    return {"ok": True}

@app.post("/api/spotify/prev")
def spotify_previous(_=Depends(admin_required)):
    spotify_service.client().previous_track()
    return {"ok": True}

@app.get("/api/spotify/state")
def spotify_state():
    return spotify_service.client().current_playback()

@app.get("/api/spotify/playlist-tracks")
def spotify_playlist_tracks():
    client = spotify_service.client()
    playlist_id = settings.spotify_default_playlist
    if not playlist_id:
        raise HTTPException(400, "Configura SPOTIFY_DEFAULT_PLAYLIST para listar las pistas.")
    try:
        playlist_pages = []
        page = client.playlist_items(playlist_id, limit=100, offset=0)
        while page.get("next"):
            playlist_pages.append(page)
            page = client.next(page)
    except SpotifyException:
        try:
            user_playlists = client.current_user_playlists(limit=20)
            fallback_playlist = next((item.get("id") for item in user_playlists.get("items", []) if item.get("id")), None)
            if not fallback_playlist:
                raise SpotifyException(404, -1, "No hay listas de reproducción disponibles")
            playlist_id = fallback_playlist
            playlist_pages = []
            page = client.playlist_items(playlist_id, limit=100, offset=0)
            while page.get("next"):
                playlist_pages.append(page)
                page = client.next(page)
        except SpotifyException as exc:
            return JSONResponse(status_code=502, content={"playlist_id": playlist_id, "tracks": [], "error": str(exc)})
    tracks = []
    for playlist_page in playlist_pages + [page]:
        for item in playlist_page.get("items", []):
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
    return {"playlist_id": playlist_id, "tracks": tracks}

@app.post("/api/spotify/play-track")
def spotify_play_track(payload: PlayTrackRequest, _=Depends(admin_required)):
    playlist_id = settings.spotify_default_playlist
    if not playlist_id:
        raise HTTPException(400, "Configura SPOTIFY_DEFAULT_PLAYLIST para reproducir una pista.")
    client = spotify_service.client()
    client.start_playback(context_uri=f"spotify:playlist:{playlist_id}", offset={"uri": payload.uri})
    try:
        client.shuffle(True)
    except SpotifyException:
        logging.warning("No se pudo activar el modo aleatorio de Spotify.")
    return {"ok": True}

@app.get("/api/clips")
def list_clips():
    if not settings.clips_folder.is_dir():
        return []
    extensions = {".mp4", ".webm", ".mov", ".m4v"}
    return [f"/clips/{quote(path.name)}" for path in sorted(settings.clips_folder.iterdir()) if path.is_file() and path.suffix.lower() in extensions]

@app.get("/clips/{filename}")
def clip_file(filename: str):
    if Path(filename).name != filename:
        raise HTTPException(404)
    path = settings.clips_folder / filename
    if not path.is_file() or path.suffix.lower() not in {".mp4", ".webm", ".mov", ".m4v"}:
        raise HTTPException(404)
    return FileResponse(path)

@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True: await ws.receive_text()
    except Exception: manager.disconnect(ws)
