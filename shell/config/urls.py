from django.urls import include, path

urlpatterns = [
    path("", include("accounts.urls")),
    path("", include("bridge.urls")),
    path("", include("phase2_feedback.urls")),
    path("researcher/", include("monitor.urls")),
]
