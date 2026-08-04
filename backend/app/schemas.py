from datetime import datetime
from pydantic import BaseModel, Field
from .models import ImageStatus
class Token(BaseModel): access_token: str; token_type: str = "bearer"
class LoginRequest(BaseModel): username: str = Field(min_length=1); password: str = Field(min_length=1)
class PhotoOut(BaseModel):
    id: int; user_name: str; original_filename: str; status: ImageStatus; version: int; uploaded_at: datetime; reviewed_at: datetime | None; url: str
class PhotoPage(BaseModel): items: list[PhotoOut]; total: int; page: int; page_size: int
class StatusChange(BaseModel): status: ImageStatus; version: int = Field(ge=1)
class CounterResponse(BaseModel): value: int
class CounterChangeRequest(BaseModel): amount: int = Field(default=1, ge=1)
class CounterSetRequest(BaseModel): value: int = Field(ge=0)
class PlayTrackRequest(BaseModel): uri: str = Field(pattern=r"^spotify:track:")
