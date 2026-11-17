"""Manual owner-authorized read-only MOJ PROP v1.4.1 MariaDB readiness scan.

Example: python manage.py mojprop_v141_db_preflight --database default

READ ONLY: issues three SELECT statements, does not mutate migrations,
tables, customer accounts, payments, orders, files or server settings.
A passing diagnostics result NEVER grants authorization to migrate/deploy.
"""
from dataclasses import asdict
import json

from django.core.management.base import BaseCommand
from django.db import connections

from prop_firm.plan1_v141_mariadb_preflight import inspect_v141_mariadb_read_only


class Command(BaseCommand):
    help = (
        "READ-ONLY: report v1.4.1 MOJ PROP MariaDB migration prerequisites. "
        "Never executes a migration or enables any financial operation."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--database", default="default",
            help="Configured Django database alias (default: default)",
        )

    def handle(self, *args, **options):
        alias = options["database"]
        try:
            connection = connections[alias]
        except Exception:
            # Do not disclose configured connection aliases to callers.
            report = {
                "connected": False,
                "schema_status": "UNKNOWN",
                "reasons": ["requested_database_alias_unavailable"],
                "migration_authorized": False,
                "release_authorized": False,
            }
        else:
            report = asdict(inspect_v141_mariadb_read_only(connection))
        self.stdout.write(json.dumps(
            report, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        ))
