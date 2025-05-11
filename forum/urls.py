from django.urls import path

from .views import ForumDemoView

urlpatterns = [
    path("forum_demo/", ForumDemoView.as_view(), name="forum_demo"),
]
