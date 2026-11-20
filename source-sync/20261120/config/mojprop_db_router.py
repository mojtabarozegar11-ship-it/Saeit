"""Fail-closed database routing for the isolated English MOJ PROP simulation state.

This module is review-only until the dedicated alias is explicitly wired into
settings. It never routes legacy prop_firm models or auth-backed models.
"""

MOJPROP_DB_ALIAS = "mojprop"

ISOLATED_MODEL_LABELS = frozenset(
    {
        "prop_firm.propsimulationidentity",
        "prop_firm.propsimulationinvoiceowner",
        "prop_firm.propsimulationaccount",
        "prop_firm.propsimulationloginchallenge",
        "prop_firm.propsimulationevent",
    }
)


def _label_for_model(model_or_instance):
    meta = getattr(model_or_instance, "_meta", None)
    return (getattr(meta, "label_lower", "") or "").lower()


def _is_isolated(model_or_instance):
    return _label_for_model(model_or_instance) in ISOLATED_MODEL_LABELS


class MojPropDatabaseRouter:
    """Keep simulation state physically separate and reject accidental leakage."""

    def db_for_read(self, model, **hints):
        if _is_isolated(model):
            return MOJPROP_DB_ALIAS
        return None

    def db_for_write(self, model, **hints):
        if _is_isolated(model):
            return MOJPROP_DB_ALIAS
        return None

    def allow_relation(self, obj1, obj2, **hints):
        left_isolated = _is_isolated(obj1)
        right_isolated = _is_isolated(obj2)
        if left_isolated or right_isolated:
            # A simulation object may relate only to another isolated object.
            return left_isolated and right_isolated
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        label = ""
        if app_label and model_name:
            label = f"{app_label}.{model_name}".lower()
        if not label:
            hinted_model = hints.get("model")
            label = _label_for_model(hinted_model)

        if db == MOJPROP_DB_ALIAS:
            # Fail closed: no auth, legacy prop_firm, admin, or unrelated table
            # may be created in the dedicated runtime database.
            return label in ISOLATED_MODEL_LABELS

        if label in ISOLATED_MODEL_LABELS:
            # The five isolated models must never be created in the factory DB.
            return False

        return None
