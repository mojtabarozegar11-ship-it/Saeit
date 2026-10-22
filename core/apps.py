from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Trigger only on paid-order saves, then recheck durable payment proof.
        from . import purchase_signals  # noqa: F401
