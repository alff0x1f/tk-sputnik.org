from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="demo-index"),
    path("forum/", views.forum, name="demo-forum"),
    path("members/", views.members, name="demo-members"),
]
