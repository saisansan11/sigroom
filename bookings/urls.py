from django.urls import path

from . import lodging_views, views

app_name = "bookings"

urlpatterns = [
    path("", views.calendar_view, name="calendar"),
    path("api/calendar/events/", views.calendar_events, name="calendar_events"),
    path("book/", views.book_search, name="book_search"),
    path("book/<str:code>/", views.book_form, name="book_form"),
    path("book/<str:code>/series/preview/", views.series_preview, name="series_preview"),
    path("book/<str:code>/series/create/", views.series_create, name="series_create"),
    path("series/<uuid:id>/", views.series_detail, name="series_detail"),
    path("series/<uuid:id>/cancel-remaining/", views.series_cancel_remaining, name="series_cancel_remaining"),
    path("bookings/mine/", views.my_bookings, name="my_bookings"),
    path("bookings/<uuid:id>/", views.booking_detail, name="booking_detail"),
    path("bookings/<uuid:id>/edit/", views.booking_edit, name="booking_edit"),
    path("bookings/<uuid:id>/amend/", views.booking_amend, name="booking_amend"),
    path("bookings/<uuid:id>/preempt/", views.booking_preempt, name="booking_preempt"),
    path("bookings/<uuid:id>/cancel/", views.booking_cancel, name="booking_cancel"),
    path("bookings/<uuid:id>/submit/", views.booking_submit, name="booking_submit"),
    path("bookings/<uuid:id>/delete/", views.booking_delete_draft, name="booking_delete_draft"),
    path("amendments/<uuid:id>/withdraw/", views.amendment_withdraw, name="amendment_withdraw"),
    path("preemptions/<uuid:id>/acknowledge/", views.preemption_acknowledge, name="preemption_acknowledge"),
    # ที่พักหลักสูตร
    path("lodging/", lodging_views.lodging_index, name="lodging_index"),
    path("lodging/manage/", lodging_views.lodging_manage, name="lodging_manage"),
    path("lodging/cohorts/<slug:slug>/", lodging_views.lodging_cohort_detail, name="lodging_cohort_detail"),
    path("lodging/cohorts/<slug:slug>/edit/", lodging_views.lodging_cohort_edit, name="lodging_cohort_edit"),
    path("lodging/cohorts/<slug:slug>/export/", lodging_views.lodging_cohort_export_csv, name="lodging_cohort_export_csv"),
    path("lodging/cohorts/<slug:slug>/qr.svg", lodging_views.lodging_cohort_qr_svg, name="lodging_cohort_qr_svg"),
    path("lodging/c/<slug:slug>/", lodging_views.lodging_portal, name="lodging_portal"),
    path("lodging/c/<slug:slug>/book/", lodging_views.lodging_book_bed, name="lodging_book_bed"),
    path("lodging/c/<slug:slug>/pass/<uuid:student_id>/", lodging_views.lodging_pass, name="lodging_pass"),
    path("lodging/checkin/<uuid:student_id>/", lodging_views.lodging_checkin, name="lodging_checkin"),
    path("lodging/checkin/<uuid:student_id>/qr.svg", lodging_views.lodging_checkin_qr_svg, name="lodging_checkin_qr_svg"),
]
