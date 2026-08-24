from django.urls import path

from . import views

app_name = "usage"

urlpatterns = [
    path("", views.usage_list, name="list"),
    path("<uuid:id>/status/", views.usage_update, name="update"),
]

