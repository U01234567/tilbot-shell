from django.conf import settings


def study(request):
    """Give every template the study's settings, and what base.html needs for the shell's mark."""
    return {"study": settings.STUDY, "shell_version": settings.SHELL_VERSION, "development": settings.DEBUG}
