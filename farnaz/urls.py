from django.urls import path

from . import views

app_name = "farnaz"
urlpatterns = [
    path("", views.home, name="home"),
    path("inquiry/", views.submit_inquiry, name="inquiry"),
]
