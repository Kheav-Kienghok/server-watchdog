# telegram-ops-notifier

FastAPI sub-app that receives a `success` / `failed` report with a domain name and forwards it to a Telegram bot.

- **success** → the app connects to the domain over TLS, confirms the certificate is valid and has a fresh ~90 days left (`CERT_MIN_VALID_DAYS`, default 85), then sends one combined Telegram message (confirmed, or "success reported but NOT confirmed").
- **failed** → sends a failure message with the domain.
- **Heartbeat** → a "still running" message at 09:00, 11:00, 14:00, 16:00, 21:00 (`TIMEZONE`, default Asia/Phnom_Penh; Mon–Fri + Sun by default).

No authentication: keep it on an internal network / restricted by firewall.

## Layout

```
src/main.py                 parent app (mounts the sub-app)
src/hook_receiver/          the sub-app package
  app.py       routes + lifespan (starts the heartbeat scheduler)
  service.py   hook processing, cert confirmation, messages
  cert.py      TLS certificate check
  scheduler.py APScheduler cron jobs
  telegram.py  Telegram sender
```

## Mount in your main project

```python
from hook_receiver import app as hook_receiver_app, lifespan

app = FastAPI(lifespan=lifespan)            # required: starts the heartbeat
app.mount("/hook-receiver", hook_receiver_app)
```

Starlette does not run a mounted sub-app's lifespan, so the parent must pass `lifespan`. If your parent already has a lifespan, call `build_scheduler(...)` / `.start()` inside it. Run a **single** worker, otherwise heartbeats are sent once per worker.

## Run

```bash
cp .env.example .env     # fill in token + chat id
docker compose up -d --build
```

Local: `pip install -r requirements.txt && cd src && uvicorn main:app --env-file ../.env`

## Send a hook

```bash
curl -X POST http://localhost:8000/hook-receiver/hook \
  -H "Content-Type: application/json" \
  -d '{"status": "success", "domain": "example.com"}'
```

Returns `202` immediately; the cert check (with retries in case the web server hasn't reloaded yet) and the Telegram message happen in the background. See `examples/certbot-deploy-hook.sh` for the certbot side.

## Release (Docker image on tag push)

`.github/workflows/docker-publish.yml` builds and pushes `ghcr.io/<owner>/<repo>` when you push a `v*` tag:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

Tags produced: `1.0.0`, `1.0`, `latest`. Use it with `NOTIFIER_IMAGE=ghcr.io/<owner>/<repo>:1.0.0 docker compose up -d`.

## Tests

```bash
pip install -r requirements-dev.txt && pytest
```
