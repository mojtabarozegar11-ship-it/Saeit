from django.urls import path

from .public_views import public_applicant_intake

urlpatterns = [
    path(
        "applicants/",
        public_applicant_intake,
        name="moj_prop_public_applicant_intake",
    ),
]
