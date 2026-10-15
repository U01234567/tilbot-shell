from django.contrib.auth import views as auth_views
from django.urls import path

from monitor import views

urlpatterns = [
    path("", views.overview, name="researcher"),
    path("export", views.export, name="export"),
    path("login", auth_views.LoginView.as_view(template_name="monitor/login.html"), name="login"),
    path("logout", auth_views.LogoutView.as_view(), name="logout"),
]
