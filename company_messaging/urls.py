from django.urls import path
from . import views

app_name = "company_messaging"
urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("new/", views.compose, name="compose"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/read/", views.mark_read, name="mark_read"),
]
