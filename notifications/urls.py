from django.urls import path

from . import views
from .push import push_enabled

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("read-all/", views.read_all, name="read_all"),
    path("<int:id>/open/", views.open_notification, name="open"),
]

if push_enabled():
    from . import push_views

    urlpatterns += [
        path("push/status/", push_views.push_status, name="push_status"),
        path("push/subscribe/", push_views.push_subscribe, name="push_subscribe"),
        path("push/unsubscribe/", push_views.push_unsubscribe, name="push_unsubscribe"),
    ]
