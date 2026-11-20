"""Fail-closed routing for the root-runtime MOJ PROP simulation app."""

MOJPROP_DB_ALIAS = "mojprop"

ISOLATED_MODEL_LABELS = frozenset({
    "prop_firm.propsimulationidentity",
    "prop_firm.propsimulationinvoiceowner",
    "prop_firm.propsimulationaccount",
    "prop_firm.propsimulationloginchallenge",
    "prop_firm.propsimulationevent",
    "prop_firm.propsimulationpayment",
    "prop_firm.propsimulationpayoutcommitment",
})


def _label_for_model(model_or_instance):
    meta = getattr(model_or_instance, "_meta", None)
    return (getattr(meta, "label_lower", "") or "").lower()


def _is_isolated(model_or_instance):
    return _label_for_model(model_or_instance) in ISOLATED_MODEL_LABELS


class MojPropDatabaseRouter:
    """Keep isolated simulation and payment models separate from all legacy state."""

    def db_for_read(self, model, **hints):
        return MOJPROP_DB_ALIAS if _is_isolated(model) else None

    def db_for_write(self, model, **hints):
        return MOJPROP_DB_ALIAS if _is_isolated(model) else None

    def allow_relation(self, obj1, obj2, **hints):
        left = _is_isolated(obj1)
        right = _is_isolated(obj2)
        if left or right:
            return left and right
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        label = ""
        if app_label and model_name:
            label = f"{app_label}.{model_name}".lower()
        if not label:
            label = _label_for_model(hints.get("model"))

        if db == MOJPROP_DB_ALIAS:
            return label in ISOLATED_MODEL_LABELS
        if label in ISOLATED_MODEL_LABELS:
            return False
        return None
