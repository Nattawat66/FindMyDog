from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.cache import cache
from .tasks import retrain_model

scheduler = BackgroundScheduler(timezone="Asia/Bangkok")

def update_scheduler():
    scheduler.remove_all_jobs()

    active = cache.get("AUTO_TRAIN_ACTIVE", False)
    time_str = cache.get("AUTO_TRAIN_TIME")  # "14:30"
    freq = cache.get("AUTO_TRAIN_FREQ", "daily")

    if not active or not time_str:
        print("Scheduler: not active or no time set")
        return

    hour, minute = map(int, time_str.split(":"))

    trigger = CronTrigger(hour=hour, minute=minute)

    scheduler.add_job(
        retrain_model,
        trigger=trigger,
        id="auto_retrain",
        replace_existing=True
    )

    print(f"Scheduler set at {hour}:{minute} every day")

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        update_scheduler()
