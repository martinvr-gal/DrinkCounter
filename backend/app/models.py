import enum
from datetime import datetime
from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class ImageStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class Photo(Base):
    __tablename__ = "photos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_name: Mapped[str] = mapped_column(String(120), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    path: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[ImageStatus] = mapped_column(Enum(ImageStatus), default=ImageStatus.PENDING, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
