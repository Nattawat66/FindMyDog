from django.apps import AppConfig


class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'
    
    def ready(self):
        # Import signals เพื่อให้ Django โหลด signal handlers
        import myapp.signals