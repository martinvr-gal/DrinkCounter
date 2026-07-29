import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile
from .models import ImageStatus

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
        return name, f"pending/{name}"
    def move(self, stored_filename: str, previous: ImageStatus, target: ImageStatus) -> str:
        source = self.root / self._folder(previous) / stored_filename
        destination = self.root / self._folder(target) / stored_filename
        if source != destination and source.exists(): shutil.move(str(source), str(destination))
        return f"{self._folder(target)}/{stored_filename}"
