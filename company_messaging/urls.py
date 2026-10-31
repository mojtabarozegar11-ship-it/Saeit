from django.urls import path
from . import views

app_name = "company_messaging"
urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("new/", views.compose, name="compose"),
    path("contacts/", views.contacts, name="contacts"),
    path("contacts/new/", views.contact_create, name="contact_create"),
    path("contacts/<int:pk>/edit/", views.contact_edit, name="contact_edit"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/read/", views.mark_read, name="mark_read"),
]
