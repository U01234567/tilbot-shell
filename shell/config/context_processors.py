from django.conf import settings


def study(request):
    """Make the study settings available to every template as {{ study }}."""
    return {"study": settings.STUDY}
