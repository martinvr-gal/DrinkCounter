import logging
from datetime import datetime
from pathlib import Path
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from .auth import admin_required, create_token
from .config import get_settings
from .database import Base, engine, get_db
from .models import ImageStatus, Photo
from .schemas import LoginRequest, PhotoOut, PhotoPage, StatusChange, Token
from .storage import LocalStorage
from .websocket import manager

logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}')
settings = get_settings(); storage = LocalStorage(settings.upload_folder)
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

@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True: await ws.receive_text()
    except Exception: manager.disconnect(ws)
