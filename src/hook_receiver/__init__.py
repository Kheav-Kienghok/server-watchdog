"""Hook receiver sub-app.

Receives a `success` / `failed` report plus a domain name, confirms the
certificate on success, and forwards the result to Telegram. Also sends a
scheduled "still running" heartbeat.

Usage in the parent project:

    from hook_receiver import app as hook_receiver_app, lifespan

    app = FastAPI(lifespan=lifespan)          # starts the heartbeat scheduler
    app.mount("/hook-receiver", hook_receiver_app)
"""

from .app import app, lifespan

__all__ = ["app", "lifespan"]
