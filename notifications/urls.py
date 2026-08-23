from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("read-all/", views.read_all, name="read_all"),
    path("<int:id>/open/", views.open_notification, name="open"),
]
