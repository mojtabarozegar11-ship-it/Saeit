from django.apps import AppConfig


class NativeCheckoutConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mpw_native_checkout"
    verbose_name = "MojPlayWin Native Coin Checkout (Staging)"

    def ready(self):
        # Registers inactive-app-only post-commit hooks.
        from . import signals  # noqa: F401
