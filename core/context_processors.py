from django.conf import settings

from tools import ai_service


def ai_status(request):
    return {
        "ai_configured": ai_service.is_configured(),
        "ai_provider": settings.AI_PROVIDER,
        "ai_model": settings.AI_MODEL,
    }
