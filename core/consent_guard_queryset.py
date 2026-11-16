"""Fail-closed ORM policy for contact consent across MOJ PROP and bot leads.

Admin and individual save() can move a real lead to 'contacted' after review.
QuerySet.update()/bulk_update() may only WITHDRAW consent, never bulk promote
a withdrawn lead back into a contactable state. Raw SQL remains out-of-scope.
"""
from django.core.exceptions import ValidationError
from django.db import models


# An opt-out is bound to the exact originally consented email and offer.
IMMUTABLE_ORIGIN_FIELDS = frozenset((
    "email", "plan_code", "brand", "source_host",
    "source_language", "consent_version",
))


class ConsentStatusQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if IMMUTABLE_ORIGIN_FIELDS.intersection(kwargs):
            raise ValidationError({
                "email": "Bulk changes to consent identity or origin are prohibited"
            })
        if "status" in kwargs:
            if (kwargs["status"] != "withdrawn"
                    or set(kwargs) - {"status", "updated_at"}):
                raise ValidationError({
                    "status": "Bulk status promotion is prohibited; use a validated model save"
                })
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        # Django implements bulk_update with update(CASE...) inside an atomic
        # block. Reject before entering that block so a denied operation
        # cannot leave an ambient TestCase/request transaction rollback-only.
        # An operator may batch-withdraw via update(status="withdrawn"), but
        # any promotion requires per-record model validation and consent.
        if "status" in fields or IMMUTABLE_ORIGIN_FIELDS.intersection(fields):
            raise ValidationError({
                "status": "Bulk changes to consent or lead identity are prohibited"
            })
        return super().bulk_update(objs, fields, batch_size=batch_size)
