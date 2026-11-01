from django.urls import include, path
from . import views
from . import trial_balance as reports
from . import project_register as projects
from . import calendar as calendar_views

app_name = "enterprise_portal"

urlpatterns = [
    path("assets/app.css", views.office_stylesheet, name="office_css"),
    path("secure-login/", views.CompanyLogin.as_view(), name="login"),
    path("logout/", views.CompanyLogout.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("finance/", views.finance, name="finance"),
    path("finance/authoritative/", views.authoritative_finance, name="authoritative_finance"),
    path("ecosystem/", include("ecosystem_hub.urls")),
    path("finance/trial-balance/", reports.trial_balance, name="trial_balance"),
    path("finance/trial-balance.csv", reports.trial_balance_csv, name="trial_balance_csv"),
    path("inventory/", views.inventory, name="inventory"),
    path("projects/", projects.project_register, name="project_register"),
    path("projects/new/", projects.new_project, name="new_project"),
    path("projects/<int:pk>/", projects.project_register, name="project_detail"),
    path("calendar/", calendar_views.calendar_view, name="calendar"),
    path("calendar/meetings/new/", calendar_views.new_meeting, name="new_meeting"),
    path("calendar/meetings/<int:pk>.ics", calendar_views.meeting_ics, name="meeting_ics"),
    path("tasks/", views.tasks, name="tasks"),
    path("tasks/new/", views.new_task, name="new_task"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("letters/", views.letters, name="letters"),
    path("letters/new/", views.new_letter, name="new_letter"),
    path("letters/attachments/<int:pk>/download/", views.download_office_attachment, name="download_office_attachment"),
]
