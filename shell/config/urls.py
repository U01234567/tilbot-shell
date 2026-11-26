from django.conf import settings
from django.urls import include, path

urlpatterns = [
    path("", include("accounts.urls")),
    path("", include("bridge.urls")),
    path("", include("phase2_feedback.urls")),
    path("researcher/", include("monitor.urls")),
]

if "extension" in settings.INSTALLED_APPS:  # a study's own code (config/settings.py): its pages come first
    urlpatterns.insert(0, path("", include("extension.urls")))
