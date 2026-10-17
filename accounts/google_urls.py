from django.urls import path
from . import google_views

urlpatterns = [
    path("google/login/", google_views.google_login, name="google_login"),
    path("google/login/callback/", google_views.google_callback, name="google_callback"),
    path("social/error/", google_views.google_error, name="socialaccount_login_error"),
]
