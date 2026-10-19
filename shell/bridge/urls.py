from django.urls import path

from bridge import views

urlpatterns = [
    path("chat", views.chat, name="chat"),
    path("bridge/save", views.save),
    path("bridge/log", views.log),
    path("bridge/ask", views.ask),
    path("bridge/status", views.status),
]
