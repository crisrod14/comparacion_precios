"""
Scheduler for automated price comparison runs.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


def create_scheduler(job_func, hour: int = 8, minute: int = 0) -> BackgroundScheduler:
    """Create and return a configured scheduler."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        job_func,
        CronTrigger(hour=hour, minute=minute),
        id="price_comparison",
        replace_existing=True,
    )
    return scheduler
