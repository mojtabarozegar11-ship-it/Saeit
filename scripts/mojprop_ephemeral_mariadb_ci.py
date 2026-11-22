"""Hermetic GitHub Actions MariaDB proof. No production data, credentials or endpoints."""
import os
import sys
from pathlib import Path

# Calling Python on a script path adds scripts/, not the repository root, to sys.path.
# Resolve the checked-out repository explicitly; never use external PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    assert os.environ.get("GITHUB_ACTIONS") == "true", "GitHub Actions only"
    assert os.environ.get("CI_MOJPROP_EPHEMERAL_DB_ONLY") == "yes"
    assert os.environ.get("CI_DB_HOST") == "127.0.0.1", "Loopback only"
    password = os.environ["CI_DB_ROOT_PASSWORD"]
    assert password.startswith("ci-temporary-"), "Reject production credentials"

    import MySQLdb
    import django
    from django.conf import settings

    dbnames = ("mpw_ci_legacy_only", "mpw_ci_mojprop_only")
    admin = MySQLdb.connect(host="127.0.0.1", port=3306, user="root", passwd=password)
    admin.autocommit(True)
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = str(cursor.fetchone()[0])
            assert "MariaDB" in version, "MariaDB required: " + version
            for name in dbnames:
                cursor.execute("CREATE DATABASE IF NOT EXISTS `" + name +
                               "` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    finally:
        admin.close()

    base = {
        "ENGINE": "django.db.backends.mysql",
        "USER": "root",
        "PASSWORD": password,
        "HOST": "127.0.0.1",
        "PORT": "3306",
        "OPTIONS": {"init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
    }
    assert not settings.configured, "Never reuse production settings"
    settings.configure(
        SECRET_KEY="ci-ephemeral-only",
        INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth",
                        "prop_firm.apps.MojPropConfig"],
        DATABASES={"default": {**base, "NAME": dbnames[0]},
                   "mojprop": {**base, "NAME": dbnames[1]}},
        DATABASE_ROUTERS=["config.mojprop_db_router.MojPropDatabaseRouter"],
        USE_TZ=True,
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )
    django.setup()
    from django.core.management import call_command
    from django.db import connections
    from django.db.migrations.loader import MigrationLoader
    from config.mojprop_db_router import MojPropDatabaseRouter
    from prop_firm.models import PropSimulationPayment

    policy = MojPropDatabaseRouter()
    assert policy.allow_migrate("default", "prop_firm", "propsimulationpayment") is False
    assert policy.allow_migrate("mojprop", "prop_firm", "propsimulationpayment") is True

    for alias in ("default", "mojprop"):
        call_command("migrate", database=alias, interactive=False, verbosity=0)
        loader = MigrationLoader(connections[alias])
        leaf = ("prop_firm", "0011_state_only_bridge")
        assert loader.graph.leaf_nodes("prop_firm") == [leaf], alias
        assert leaf in loader.applied_migrations, alias
        print("CI MariaDB migration history applied:", alias, flush=True)

    legacy = {
        "proptrader", "propaccount", "propexecution", "propequityobservation",
        "propdecisionlog", "propprofitallocation", "propprofitjournalline",
        "propsocialevidence", "propchallengeenrollment", "propinterest",
        "tronsettlementledger", "propplan1invoice", "propplan1receipt",
        "proprewardreserveallocation", "proprewardcommitment",
    }
    simulated = {
        "propsimulationidentity", "propsimulationinvoiceowner",
        "propsimulationaccount", "propsimulationloginchallenge",
        "propsimulationevent", "propsimulationpayment",
        "propsimulationpayoutcommitment",
    }
    tables = {}
    for alias in ("default", "mojprop"):
        connection = connections[alias]
        with connection.cursor() as cursor:
            names = connection.introspection.table_names(cursor)
        tables[alias] = {name.removeprefix("prop_firm_") for name in names
                         if name.startswith("prop_firm_")}
        print("Isolated synthetic tables:", alias, len(tables[alias]), flush=True)

    assert legacy <= tables["default"], "Historical tables missing on default"
    assert not (simulated & tables["default"]), "Simulation models leaked into default"
    assert simulated <= tables["mojprop"], "Simulation tables missing on mojprop"
    assert not (legacy & tables["mojprop"]), "Historical models leaked into mojprop"

    conn = connections["mojprop"]
    with conn.cursor() as cursor:
        constraints = conn.introspection.get_constraints(
            cursor, PropSimulationPayment._meta.db_table)
    receiver_unique = [
        key for key, data in constraints.items()
        if data.get("unique") and data.get("columns") == ["recipient"]
    ]
    assert len(receiver_unique) == 1, "Missing native MariaDB UNIQUE(recipient)"
    print("PASS: native MariaDB dual database separation, 15 historical and 7 "
          "simulation tables, recipient uniqueness and state-only bridge.", flush=True)
    print("PRODUCTION_DB_ACCESS=0; PRODUCTION_BACKUP_ACCESS=0", flush=True)


if __name__ == "__main__":
    main()
