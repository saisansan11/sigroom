from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("", views.calendar_view, name="calendar"),
    path("api/calendar/events/", views.calendar_events, name="calendar_events"),
    path("book/", views.book_search, name="book_search"),
    path("book/<str:code>/", views.book_form, name="book_form"),
    path("bookings/mine/", views.my_bookings, name="my_bookings"),
    path("bookings/<uuid:id>/", views.booking_detail, name="booking_detail"),
    path("bookings/<uuid:id>/edit/", views.booking_edit, name="booking_edit"),
    path("bookings/<uuid:id>/cancel/", views.booking_cancel, name="booking_cancel"),
    path("bookings/<uuid:id>/submit/", views.booking_submit, name="booking_submit"),
    path("bookings/<uuid:id>/delete/", views.booking_delete_draft, name="booking_delete_draft"),
]
