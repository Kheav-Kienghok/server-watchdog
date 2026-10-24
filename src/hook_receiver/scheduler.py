from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Settings
from .service import send_heartbeat


def build_scheduler(settings: Settings, started_at: datetime) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    for hour, minute in settings.healthcheck_times:
        scheduler.add_job(
            send_heartbeat,
            CronTrigger(
                hour=hour,
                minute=minute,
                day_of_week=settings.healthcheck_days,
                timezone=settings.timezone,
            ),
            args=[settings, started_at],
            id=f"heartbeat-{hour:02d}{minute:02d}",
            coalesce=True,
            misfire_grace_time=300,
            replace_existing=True,
        )
    return scheduler
