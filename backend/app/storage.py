import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from .models import ImageStatus


def normalize_orientation(path: Path) -> bool:
    """Bake an EXIF rotation into an image so every browser gets its true size."""
    try:
        with Image.open(path) as image:
            if image.getexif().get(274, 1) == 1:
                return False
            normalized = ImageOps.exif_transpose(image)
            image_format = image.format
            if image_format == "JPEG" and normalized.mode not in {"RGB", "L"}:
                normalized = normalized.convert("RGB")
            normalized.save(path, format=image_format)
            return True
    except (OSError, UnidentifiedImageError):
        return False

class Storage(ABC):
    @abstractmethod
    def save_pending(self, file: UploadFile) -> tuple[str, str]: ...
    @abstractmethod
    def move(self, stored_filename: str, previous: ImageStatus, target: ImageStatus) -> str: ...

class LocalStorage(Storage):
    def __init__(self, root: Path):
        self.root = root
        for folder in ("pending", "approved", "rejected"): (root / folder).mkdir(parents=True, exist_ok=True)
    def _folder(self, status: ImageStatus) -> str: return status.value.lower()
    def save_pending(self, file: UploadFile) -> tuple[str, str]:
        suffix = Path(file.filename or "image.jpg").suffix.lower() or ".jpg"
        name = f"{uuid4().hex}{suffix}"
        destination = self.root / "pending" / name
        with destination.open("wb") as out: shutil.copyfileobj(file.file, out)
        normalize_orientation(destination)
        return name, f"pending/{name}"
    def move(self, stored_filename: str, previous: ImageStatus, target: ImageStatus) -> str:
        source = self.root / self._folder(previous) / stored_filename
        destination = self.root / self._folder(target) / stored_filename
        if source != destination and source.exists(): shutil.move(str(source), str(destination))
        return f"{self._folder(target)}/{stored_filename}"
