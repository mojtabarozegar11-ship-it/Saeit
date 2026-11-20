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
)


def test_only_five_models_are_isolated():
    labels = {
        model._meta.label_lower
        for model in (
            PropSimulationIdentity,
            PropSimulationInvoiceOwner,
            PropSimulationAccount,
            PropSimulationLoginChallenge,
            PropSimulationEvent,
        )
    }
    assert labels == set(ISOLATED_MODEL_LABELS)


def test_isolated_models_have_no_auth_user_relation():
    user_model = get_user_model()
    for model in (
        PropSimulationIdentity,
        PropSimulationInvoiceOwner,
        PropSimulationAccount,
        PropSimulationLoginChallenge,
        PropSimulationEvent,
    ):
        assert all(
            not (
                field.is_relation
                and getattr(field.remote_field, "model", None) is user_model
            )
            for field in model._meta.get_fields()
        )


def test_router_allows_only_isolated_models_on_mojprop():
    router = MojPropDatabaseRouter()
    assert router.allow_migrate(
        MOJPROP_DB_ALIAS, "prop_firm", "propsimulationidentity"
    ) is True
    assert router.allow_migrate(
        MOJPROP_DB_ALIAS, "auth", "user"
    ) is False
    assert router.allow_migrate(
        "default", "prop_firm", "propsimulationidentity"
    ) is False
