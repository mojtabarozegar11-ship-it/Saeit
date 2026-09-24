import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_claim_missing_task_returns_404():
    user = get_user_model().objects.create_user(
        username="runtime-missing", password="pass", is_staff=True
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post("/api/tasks/999999/claim/", {}, format="json")

    assert response.status_code == 404
    assert response.data["detail"] == "Task not found."
