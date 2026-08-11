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
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    settings.clips_folder.mkdir(parents=True, exist_ok=True)
    if not spotify_service.has_token() or not settings.spotify_autoplay:
        return
    try:
        if spotify_service.start_default_playlist():
            logging.info("Se solicitó iniciar la playlist configurada de Spotify.")
    except Exception as exc:
        # No stop the gallery if Spotify is temporarily unavailable or there is
        # no active playback device. The controls remain available to retry.
        logging.warning("No se pudo iniciar Spotify automáticamente: %s", exc)

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

@app.get("/api/health")
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

@app.post("/api/upload", response_model=PhotoOut, status_code=status.HTTP_201_CREATED)
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

@app.post("/api/admin/login", response_model=Token)
def login(payload: LoginRequest):
    if payload.username != settings.admin_username or payload.password != settings.admin_password: raise HTTPException(401, "Credenciales incorrectas")
    return Token(access_token=create_token(payload.username))

@app.get("/api/admin/pending", response_model=PhotoPage)
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

@app.post("/api/admin/approve/{photo_id}", response_model=PhotoOut)
async def approve(photo_id: int, payload: StatusChange, db: Session = Depends(get_db), _=Depends(admin_required)): return await change_photo(photo_id, payload, db, ImageStatus.APPROVED)
@app.post("/api/admin/reject/{photo_id}", response_model=PhotoOut)
async def reject(photo_id: int, payload: StatusChange, db: Session = Depends(get_db), _=Depends(admin_required)): return await change_photo(photo_id, payload, db, ImageStatus.REJECTED)

@app.post("/api/admin/status/{photo_id}", response_model=PhotoOut)
async def set_status(photo_id: int, payload: StatusChange, db: Session = Depends(get_db), _=Depends(admin_required)):
    """Move a photo between any moderation folders while preserving its history."""
    return await change_photo(photo_id, payload, db, payload.status)

@app.get("/api/gallery/{gallery_status}", response_model=PhotoPage)
def gallery(gallery_status: str, page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100), search: str | None = None, order: str = Query("desc", pattern="^(asc|desc)$"), db: Session = Depends(get_db)):
    try: target = None if gallery_status == "all" else ImageStatus(gallery_status.upper())
    except ValueError: raise HTTPException(404, "Estado no válido")
    return page_query(db, target, page, page_size, search, order)

@app.get("/api/images/{folder}/{filename}")
def image_file(folder: str, filename: str):
    if folder not in {"pending", "approved", "rejected"} or Path(filename).name != filename: raise HTTPException(404)
    path = settings.upload_folder / folder / filename
    if not path.is_file(): raise HTTPException(404)
    return FileResponse(path)

@app.get("/api/admin/spotify/login")
def spotify_login(_=Depends(admin_required)):
    return RedirectResponse(spotify_service.authorize_url())

@app.get("/api/admin/spotify/authorize-url")
def spotify_authorize_url(_=Depends(admin_required)):
    return {"url": spotify_service.authorize_url()}

@app.get("/api/admin/spotify/callback")
def spotify_callback(code: str, state: str):
    spotify_service.exchange_code(code, state)
    try:
        spotify_service.start_default_playlist()
    except Exception as exc:
        logging.warning("No se pudo iniciar Spotify tras la autorización: %s", exc)
    return RedirectResponse("/spotify")

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

@app.post("/api/spotify/tv/clip-pause")
def spotify_pause_for_tv_clip():
    return {"resume_after_clip": spotify_service.pause_for_clip()}

@app.post("/api/spotify/tv/clip-resume")
def spotify_resume_after_tv_clip(resume_after_clip: bool = False):
    return {"resumed": spotify_service.resume_after_clip(resume_after_clip)}

@app.get("/api/spotify/playlist-tracks")
def spotify_playlist_tracks(_=Depends(admin_required)):
    playlist_id = settings.spotify_default_playlist
    if not playlist_id:
        raise HTTPException(400, "Configura SPOTIFY_DEFAULT_PLAYLIST para listar las pistas.")
    try:
        playlist_pages = spotify_service.playlist_pages(playlist_id)
    except SpotifyException:
        try:
            client = spotify_service.client()
            user_playlists = client.current_user_playlists(limit=20)
            fallback_playlist = next((item.get("id") for item in user_playlists.get("items", []) if item.get("id")), None)
            if not fallback_playlist:
                raise SpotifyException(404, -1, "No hay listas de reproducción disponibles")
            playlist_id = fallback_playlist
            playlist_pages = spotify_service.playlist_pages(playlist_id)
        except SpotifyException as exc:
            return JSONResponse(status_code=502, content={"playlist_id": playlist_id, "tracks": [], "error": str(exc)})
    tracks = []
    for playlist_page in playlist_pages:
        for item in playlist_page.get("items", []):
            track = item.get("track") or item.get("item")
            if not track:
                continue
            tracks.append({
                "name": track.get("name"),
                "uri": track.get("uri"),
                "artists": [artist.get("name") for artist in track.get("artists", []) if artist.get("name")],
                "album": track.get("album", {}).get("name") if isinstance(track.get("album"), dict) else None,
                "image": (track.get("album", {}).get("images") or [{}])[0].get("url") if isinstance(track.get("album"), dict) else None,
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

CLIP_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
CLIP_MEDIA_TYPES = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".m4v": "video/x-m4v"}

def clip_sort_key(path: Path):
    try:
        return (0, int(path.stem), path.name.lower())
    except ValueError:
        return (1, path.name.lower())

def available_clips():
    if not settings.clips_folder.is_dir():
        return []
    clip_paths = [path for path in settings.clips_folder.iterdir() if path.is_file() and path.suffix.lower() in CLIP_EXTENSIONS]
    return [f"/api/clips/{quote(path.name)}" for path in sorted(clip_paths, key=clip_sort_key)]

def next_clip_filename(extension: str) -> str:
    numbered_clips = [path for path in settings.clips_folder.iterdir() if path.is_file() and path.suffix.lower() in CLIP_EXTENSIONS and path.stem.isdigit()]
    next_number = max((int(path.stem) for path in numbered_clips), default=0) + 1
    padding = max((len(path.stem) for path in numbered_clips), default=2)
    return f"{next_number:0{padding}d}{extension}"

@app.get("/api/clips")
def list_clips():
    return available_clips()

@app.get("/api/admin/clips")
def admin_clips(_=Depends(admin_required)):
    return available_clips()

@app.post("/api/admin/clips", status_code=status.HTTP_201_CREATED)
async def upload_clip(clip: UploadFile = File(...), _=Depends(admin_required)):
    filename = Path(clip.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in CLIP_EXTENSIONS:
        raise HTTPException(415, "Formato no permitido. Usa MP4, WebM, MOV o M4V.")
    contents = await clip.read(settings.max_clip_bytes + 1)
    if len(contents) > settings.max_clip_bytes:
        raise HTTPException(413, "El clip supera el tamaño máximo permitido.")

    settings.clips_folder.mkdir(parents=True, exist_ok=True)
    stored_filename = next_clip_filename(extension)
    (settings.clips_folder / stored_filename).write_bytes(contents)
    url = f"/api/clips/{quote(stored_filename)}"
    await manager.broadcast({"type": "clip.created", "url": url})
    return {"url": url, "filename": filename}

@app.delete("/api/admin/clips/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clip(filename: str, _=Depends(admin_required)):
    if Path(filename).name != filename:
        raise HTTPException(404)
    path = settings.clips_folder / filename
    if not path.is_file() or path.suffix.lower() not in CLIP_EXTENSIONS:
        raise HTTPException(404, "Clip no encontrado.")
    path.unlink()
    await manager.broadcast({"type": "clip.deleted", "url": f"/api/clips/{quote(filename)}"})

@app.get("/api/clips/{filename}")
def clip_file(filename: str):
    if Path(filename).name != filename:
        raise HTTPException(404)
    path = settings.clips_folder / filename
    if not path.is_file() or path.suffix.lower() not in CLIP_EXTENSIONS:
        raise HTTPException(404)
    return FileResponse(path, media_type=CLIP_MEDIA_TYPES[path.suffix.lower()])

@app.websocket("/api/ws")
async def websocket(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True: await ws.receive_text()
    except Exception: manager.disconnect(ws)
