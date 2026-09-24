import pytest
from django.contrib.auth import get_user_model
from core.models import ResearchProject
from core.services import requires_owner_approval
@pytest.mark.django_db
def test_approval_policy():
 assert requires_owner_approval("deploy","high")
 assert not requires_owner_approval("research","low")
@pytest.mark.django_db
def test_project():
 u=get_user_model().objects.create_user(username="owner")
 p=ResearchProject.objects.create(owner=u,title="Test",objective="Test")
 assert p.pk
