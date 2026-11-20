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


@pytest.mark.django_db
def test_chat_message_endpoint_does_not_expose_internal_exception(monkeypatch):
    user = get_user_model().objects.create_user(
        username="chat-error-message", password="pass"
    )

    def explode(*args, **kwargs):
        raise RuntimeError("SECRET_MESSAGE_INTERNAL")

    monkeypatch.setattr(MasterAgentChat, "respond", explode)

    client = APIClient()
    client.force_authenticate(user=user)
    created = client.post(
        "/api/master-chat/",
        {"title": "test"},
        format="json",
    )
    session_id = created.data["session"]["id"]

    response = client.post(
        f"/api/master-chat/{session_id}/messages/",
        {"message": "hello"},
        format="json",
    )

    assert response.status_code == 503
    assert "error" not in response.data
    assert "SECRET_MESSAGE_INTERNAL" not in str(response.data)


@pytest.mark.django_db
@pytest.mark.parametrize("state, expected", [
    ("executed", "direct_owner_chat_executed"),
    ("already_executed", "already_executed"),
    ("execution_in_progress", "execution_in_progress"),
    ("manual_reconciliation_required", "manual_reconciliation_required"),
    ("unexpected", "execution_unverified"),
])
def test_chat_reports_only_confirmed_execution_and_canonical_identity(monkeypatch, state, expected):
    from core.models import ChatSession
    from core import operation_executor
    from mojtaba_identity import BOT_ID
    user = get_user_model().objects.create_superuser(username="canonical-owner", password="pass", email="owner@example.org")
    session = ChatSession.objects.create(user=user, title="status evidence")
    monkeypatch.setattr(operation_executor, "execute_approved_chat_operation", lambda approval: {"status": state, "result": {"state": "fixture"}})
    reply = MasterAgentChat().respond(session, "deploy release now")
    assert reply.startswith("اجرا انجام شد.") == (state == "executed")
    record = session.messages.filter(role="assistant").latest("created_at")
    assert record.metadata["execution"] == expected
    assert record.metadata["bot_id"] == BOT_ID


def test_prompt_uses_single_canonical_bot_identity():
    from core.chat_runtime import master_system_prompt
    from mojtaba_identity import BOT_ID
    assert BOT_ID in master_system_prompt()
