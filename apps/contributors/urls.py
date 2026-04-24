from django.urls import path

from . import views

urlpatterns = [
    path("", views.contributors_view, name="contributors"),
]
