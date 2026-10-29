from django.urls import path
from . import views

app_name = "company_marketing"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("campaigns/new/", views.new_campaign, name="new_campaign"),
    path("publications/new/", views.new_publication, name="new_publication"),
    path("publications/<int:pk>/", views.detail, name="detail"),
    path("publications/<int:pk>/approve/", views.approve, name="approve"),
]
