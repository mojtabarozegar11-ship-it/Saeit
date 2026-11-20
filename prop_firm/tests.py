"""Database isolation contract for all seven explicit MOJ PROP models."""
from django.contrib.auth import get_user_model

from config.mojprop_db_router import (
    ISOLATED_MODEL_LABELS,
    MOJPROP_DB_ALIAS,
    MojPropDatabaseRouter,
)
from .models import (
    PropSimulationAccount,
    PropSimulationEvent,
    PropSimulationIdentity,
    PropSimulationInvoiceOwner,
    PropSimulationLoginChallenge,
    PropSimulationPayment,
    PropSimulationPayoutCommitment,
)


ISOLATED_MODELS = (
    PropSimulationIdentity,
    PropSimulationInvoiceOwner,
    PropSimulationAccount,
    PropSimulationLoginChallenge,
    PropSimulationEvent,
    PropSimulationPayment,
    PropSimulationPayoutCommitment,
)


def test_exactly_seven_models_are_isolated():
    labels = {model._meta.label_lower for model in ISOLATED_MODELS}
    assert len(labels) == 7
    assert labels == set(ISOLATED_MODEL_LABELS)


def test_isolated_models_have_no_auth_user_relation():
    user_model = get_user_model()
    for model in ISOLATED_MODELS:
        assert all(
            not (
                field.is_relation
                and getattr(field.remote_field, "model", None) is user_model
            )
            for field in model._meta.get_fields()
        ), model._meta.label_lower


def test_router_allows_only_isolated_models_on_mojprop():
    router = MojPropDatabaseRouter()
    for model in ISOLATED_MODELS:
        label = model._meta.model_name
        assert router.db_for_read(model) == MOJPROP_DB_ALIAS
        assert router.db_for_write(model) == MOJPROP_DB_ALIAS
        assert router.allow_migrate(MOJPROP_DB_ALIAS, "prop_firm", label) is True
        assert router.allow_migrate("default", "prop_firm", label) is False
    assert router.allow_migrate(MOJPROP_DB_ALIAS, "auth", "user") is False
    assert router.allow_migrate(MOJPROP_DB_ALIAS, "prop_firm", "unknownmodel") is False
    assert router.db_for_read(get_user_model()) is None
    assert router.db_for_write(get_user_model()) is None


def test_isolated_relations_cannot_cross_into_auth_database():
    router = MojPropDatabaseRouter()
    user = get_user_model()()
    for model in ISOLATED_MODELS:
        obj = model()
        assert router.allow_relation(obj, user) is False
        assert router.allow_relation(user, obj) is False
        assert router.allow_relation(obj, PropSimulationIdentity()) is True
