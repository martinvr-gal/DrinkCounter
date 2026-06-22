from pydantic import BaseModel, Field


class CounterResponse(BaseModel):
    value: int


class CounterChangeRequest(BaseModel):
    amount: int = Field(default=1, ge=1)


class CounterSetRequest(BaseModel):
    value: int = Field(ge=0)
