from django.urls import path

from . import views

app_name = "approvals"

urlpatterns = [
    path("", views.queue, name="queue"),
    path("<uuid:id>/approve/", views.approve, name="approve"),
    path("<uuid:id>/reject/", views.reject, name="reject"),
    path("amendments/<uuid:id>/approve/", views.amendment_approve, name="amendment_approve"),
    path("amendments/<uuid:id>/reject/", views.amendment_reject, name="amendment_reject"),
    path("series/<uuid:id>/decide/", views.series_decide, name="series_decide"),
    path("delegation/", views.delegation, name="delegation"),
    path("delegation/<int:id>/delete/", views.delegation_delete, name="delegation_delete"),
]
