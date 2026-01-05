from django.apps import AppConfig
import sys
import os

class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'
    
    def ready(self):
        # Import signals เพื่อให้ Django โหลด signal handlers
        import myapp.signals
        # print("App ready")
        # from .models import TrainingConfig
        # from .scheduler import start_scheduler
        # import threading

        # try:
        #     cfg = TrainingConfig.objects.filter(is_active=True).first()
        #     if cfg:
        #         cache.set('AUTO_TRAIN_TIME', cfg.scheduled_time, None)
        #         cache.set('AUTO_TRAIN_FREQ', cfg.frequency, None)
        #         cache.set('AUTO_TRAIN_ACTIVE', cfg.is_active, None)
        # except Exception as e:
        #     print("Skip cache load:", e)

        # threading.Thread(target=start_scheduler, daemon=True).start()
        from .scheduler import start_scheduler
        start_scheduler()