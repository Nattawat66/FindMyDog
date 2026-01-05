# scheduler.py
import time
from datetime import datetime, date
from django.core.cache import cache

def start_scheduler():
    print("Scheduler started")
    last_run = None

    while True:
        active = cache.get('AUTO_TRAIN_ACTIVE')
        sched_time = cache.get('AUTO_TRAIN_TIME')
        freq = cache.get('AUTO_TRAIN_FREQ')
        print("Cache debug1:", active, sched_time, freq)
        #ถ้า cache ว่าง โหลดจาก DB
        if active is None or sched_time is None or freq is None:
            try:
                from .models import TrainingConfig 
                cfg = TrainingConfig.objects.filter(is_active=True).first()
                if cfg:
                    active = cfg.is_active
                    sched_time = cfg.scheduled_time
                    freq = cfg.frequency

                    cache.set('AUTO_TRAIN_ACTIVE', active, None)
                    cache.set('AUTO_TRAIN_TIME', sched_time, None)
                    cache.set('AUTO_TRAIN_FREQ', freq, None)

                    print("Loaded from DB into cache:", active, sched_time, freq)
            except Exception as e:
                print("Fallback DB load failed:", e)

        print("Cache:", active, sched_time, freq)

        if active and sched_time:
            from .tasks import retrain_model

            now = datetime.now()
            now_hm = now.strftime('%H:%M')
    
            should_run = (
                (freq == 'daily' and now_hm == sched_time) or
                (freq == 'weekly' and now.weekday() == 0 and now_hm == sched_time) or
                (freq == 'monthly' and now.day == 1 and now_hm == sched_time)
            )

            if should_run and last_run != date.today():
                print("Trigger retrain...")
                retrain_model()
                last_run = date.today()
                print("Retrain completed.") 

        time.sleep(20)
