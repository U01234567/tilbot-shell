from django.urls import path

from phase2_feedback import views

urlpatterns = [
    path("results", views.results, name="results"),
]
