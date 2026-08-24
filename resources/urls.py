from django.urls import path

from . import views

app_name = "resources"

urlpatterns = [
    path("<str:code>/outage/", views.outage, name="outage"),
    path("outage/<int:id>/end/", views.outage_end, name="outage_end"),
]
