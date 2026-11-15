"""Fail-closed ORM policy for contact consent across MOJ PROP and bot leads.

Admin and individual save() can move a real lead to 'contacted' after review.
QuerySet.update()/bulk_update() may only WITHDRAW consent, never bulk promote
a withdrawn lead back into a contactable state. Raw SQL remains out-of-scope.
"""
from django.core.exceptions import ValidationError
from django.db import models


class ConsentStatusQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "status" in kwargs:
            if (kwargs["status"] != "withdrawn"
                    or set(kwargs) - {"status", "updated_at"}):
                raise ValidationError({
                    "status": "Bulk status promotion is prohibited; use a validated model save"
                })
        return super().update(**kwargs)
