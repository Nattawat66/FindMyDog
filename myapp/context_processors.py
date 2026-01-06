from django.conf import settings


def google_maps_api_key(request):
    """
    Add GOOGLE_MAPS_API_KEY from settings to every template context.
    """
    return {
        "GOOGLE_MAPS_API_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }


