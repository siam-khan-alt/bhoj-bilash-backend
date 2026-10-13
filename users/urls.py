from django.urls import path

from .views import LoginView, me

urlpatterns = [
    path("login", LoginView.as_view(), name="login"),
    path("me", me, name="me"),
]
