import logging

from fastapi import FastAPI

from hook_receiver import app as hook_receiver_app
from hook_receiver import lifespan as hook_receiver_lifespan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Parent app. Replace this with your main project's app; the two lines that
# matter are `lifespan=` and `app.mount(...)`.
app = FastAPI(title="telegram-ops-notifier", lifespan=hook_receiver_lifespan)
app.mount("/hook-receiver", hook_receiver_app)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
