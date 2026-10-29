from django.urls import path
from . import views

app_name = "company_marketing"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("campaigns/new/", views.new_campaign, name="new_campaign"),
    path("campaigns/<int:pk>/state/", views.set_campaign_state, name="set_campaign_state"),
    path("channels/new/", views.new_channel, name="new_channel"),
    path("channels/<int:pk>/verify/", views.verify_channel, name="verify_channel"),
    path("leads/new/", views.new_lead, name="new_lead"),
    path("metrics/new/", views.new_metric, name="new_metric"),
    path("publications/new/", views.new_publication, name="new_publication"),
    path("publications/<int:pk>/", views.detail, name="detail"),
    path("publications/<int:pk>/approve/", views.approve, name="approve"),
]
