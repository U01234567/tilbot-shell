from django.urls import include, path

urlpatterns = [
    path("", include("accounts.urls")),
    path("", include("bridge.urls")),
    path("researcher/", include("monitor.urls")),
]
