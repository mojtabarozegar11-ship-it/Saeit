import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.chat_runtime import MasterAgentChat


@pytest.mark.django_db
def test_chat_api_does_not_expose_internal_exception(monkeypatch):
    user = get_user_model().objects.create_user(
        username="chat-error-user", password="pass"
    )

    def explode(*args, **kwargs):
        raise RuntimeError("SECRET_INTERNAL_DATABASE_DETAIL")

    monkeypatch.setattr(MasterAgentChat, "respond", explode)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/master-chat/",
        {"title": "test", "message": "hello"},
        format="json",
    )

    assert response.status_code == 503
    assert response.data["detail"] == "Master Agent chat is temporarily unavailable."
    assert "error" not in response.data
    assert "SECRET_INTERNAL_DATABASE_DETAIL" not in str(response.data)
