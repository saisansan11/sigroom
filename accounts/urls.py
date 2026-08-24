from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("change-initial-password/", views.first_password_change, name="first_password_change"),
]

