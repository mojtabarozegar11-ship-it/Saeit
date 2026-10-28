"""Read-only guard for public catalogs during incomplete schema rollout.

Do not infer empty catalogs from a missing database table: the page must
explicitly state temporary data unavailability. This guard never migrates,
creates tables, or changes records. Connection failures still raise normally.
"""
from django.db import connection


def missing_public_tables(*models):
    """Return True if the selected database lacks any required model table."""
    existing = set(connection.introspection.table_names())
    return any(model._meta.db_table not in existing for model in models)


def mark_public_data_unavailable(response):
    """Do not cache or index incomplete public catalogs as genuine empty pages."""
    response["Cache-Control"] = "private, no-store"
    response["X-ZM-Data-Status"] = "temporarily-unavailable"
    # Keep a temporary empty catalog out of search results until recovery.
    # Do not modify the normal response path or existing canonical URLs.
    response["X-Robots-Tag"] = "noindex"
    return response
