import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI

from .config import Settings, get_settings
from .scheduler import build_scheduler
from .schemas import HookPayload, HookResponse
from .service import process_hook

logger = logging.getLogger("hook_receiver")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Starts the heartbeat scheduler.

    Starlette does NOT run a mounted sub-app's lifespan, so the parent app must
    use this (FastAPI(lifespan=lifespan)). Run with a single worker.
    """
    settings = get_settings()  # fail fast if env is missing
    scheduler = build_scheduler(settings, datetime.now(timezone.utc))
    scheduler.start()
    logger.info(
        "heartbeat scheduler started: %s on %s (%s)",
        ", ".join(f"{h:02d}:{m:02d}" for h, m in settings.healthcheck_times),
        settings.healthcheck_days,
        settings.timezone,
    )
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


router = APIRouter()


@router.post("/hook", response_model=HookResponse, status_code=202)
async def receive_hook(
    payload: HookPayload,
    background: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> HookResponse:
    background.add_task(process_hook, payload, settings)
    return HookResponse(status=payload.status, domain=payload.domain)


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


app = FastAPI(title="Hook Receiver", lifespan=lifespan)
app.include_router(router)
