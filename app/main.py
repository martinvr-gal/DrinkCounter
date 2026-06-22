from __future__ import annotations

import sys
from pathlib import Path

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

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "counter.db"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
