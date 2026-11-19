"""Read-only release preflight. Local configuration is not proof of live delivery."""
import json
from hashlib import sha256
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.urls import resolve, Resolver404
from prop_firm.models import (
    PropSimulationAccount, PropSimulationIdentity, PropSimulationLoginChallenge,
    PropSimulationInvoiceOwner, PropSimulationEvent, PropPlan1Invoice,
    PropPlan1Receipt, PropRewardReserveAllocation, TronSettlementLedger,
)
from prop_firm.simulation_invoice_contract import REQUIRED_GATES, valid_tron_recipient
from prop_firm.simulation_runtime import trading_runtime_ready

ROUTES = {
    "/moj-prop/": "moj_prop_landing",
    "/moj-prop/dashboard/": "moj_prop_dashboard",
    "/moj-prop/account/login/": "moj_prop_simulation_login",
    "/moj-prop/checkout/start/": "moj_prop_simulation_checkout",
    "/moj-prop/invoice/SIM-AUDIT/": "moj_prop_simulation_invoice",
    "/moj-prop/account/1/terminal/": "moj_prop_simulation_terminal",
}
MODELS = (PropSimulationAccount, PropSimulationIdentity, PropSimulationLoginChallenge,
          PropSimulationInvoiceOwner, PropSimulationEvent, PropPlan1Invoice,
          PropPlan1Receipt, PropRewardReserveAllocation, TronSettlementLedger)

def audit():
    routes = {}
    for path, name in ROUTES.items():
        try:
            routes[path] = resolve(path).url_name == name
        except Resolver404:
            routes[path] = False
    tables = {}
    with connection.cursor() as cursor:
        available = set(connection.introspection.table_names(cursor))
        for model in MODELS:
            name = model._meta.db_table
            if name not in available:
                tables[name] = False
                continue
            columns = {item.name for item in connection.introspection.get_table_description(cursor, name)}
            tables[name] = all(f.column in columns for f in model._meta.local_concrete_fields)
    applied = MigrationRecorder(connection).applied_migrations()
    migrations = ("prop_firm", "0017_simulation_event_head") in applied
    terms = getattr(settings, "MPW_SIMULATION_TERMS_TEXT", "")
    digest = getattr(settings, "MPW_SIMULATION_TERMS_DIGEST", "")
    config = {
        "identity_enabled": getattr(settings, "MPW_SIMULATION_IDENTITY_ENABLED", False) is True,
        "smtp_from_configured": bool(getattr(settings, "MPW_SIMULATION_FROM_EMAIL", "")),
        "smtp_backend_configured": settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend" and bool(settings.EMAIL_HOST),
        "checkout_enabled": getattr(settings, "MPW_SIMULATION_CHECKOUT_ENABLED", False) is True,
        "reconciliation_enabled": getattr(settings, "MPW_SIMULATION_RECONCILIATION_ENABLED", False) is True,
        "recipient_format_valid": valid_tron_recipient(getattr(settings, "MPW_SIMULATION_RECIPIENT", "")),
        "terms_digest_matches": isinstance(terms, str) and bool(terms.strip()) and sha256(terms.encode()).hexdigest() == digest,
        "runtime_config_valid": trading_runtime_ready(),
    }
    gates = {name: getattr(settings, "MPW_SIMULATION_"+name.upper(), False) is True for name in REQUIRED_GATES}
    return {
        "schema_columns_present": tables, "latest_migration_recorded": migrations,
        "django_routes_resolve": routes, "configuration": config, "configured_approval_flags": gates,
        "all_local_checks_pass": all(tables.values()) and migrations and all(routes.values()) and all(config.values()) and all(gates.values()),
        "externally_unverified": ["Apache/Passenger routing", "SMTP delivery", "mainnet settlement",
                                 "quote provenance", "worker liveness", "reserve custody", "legal approval",
                                 "backup recovery", "end-to-end customer delivery"],
        "commercial_release_verified": False,
    }

class Command(BaseCommand):
    help = "Inspect local MOJ PROP configuration, routes and schema without sending or changing anything."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(audit(), sort_keys=True, indent=2))
