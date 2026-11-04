from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Account(models.Model):
    class Kind(models.TextChoices):
        ASSET = "asset", "دارایی"
        LIABILITY = "liability", "بدهی"
        EQUITY = "equity", "حقوق مالکانه"
        REVENUE = "revenue", "درآمد"
        EXPENSE = "expense", "هزینه"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("code",)

    def __str__(self):
        return f"{self.code} — {self.name}"


class JournalEntry(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        POSTED = "posted", "قطعی"
        VOID = "void", "باطل"

    reference = models.CharField(max_length=40, unique=True)
    occurred_on = models.DateField()
    memo = models.CharField(max_length=300)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-occurred_on", "-id")
        indexes = [models.Index(fields=("status", "occurred_on"))]

    def __str__(self):
        return f"{self.reference} — {self.memo}"

    def validate_balanced(self):
        totals = self.lines.aggregate(debit=models.Sum("debit"), credit=models.Sum("credit"))
        debit = totals["debit"] or Decimal("0")
        credit = totals["credit"] or Decimal("0")
        if debit <= 0 or debit != credit:
            raise ValidationError("سند باید حداقل دو ردیف و جمع بدهکار و بستانکار برابر داشته باشد.")
        return debit


class JournalLine(models.Model):
    entry = models.ForeignKey(JournalEntry, related_name="lines", on_delete=models.PROTECT)
    account = models.ForeignKey(Account, related_name="journal_lines", on_delete=models.PROTECT)
    description = models.CharField(max_length=240, blank=True)
    debit = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    credit = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0, credit=0) | models.Q(credit__gt=0, debit=0)),
                name="accounting_line_one_side_only",
            )
        ]

    def clean(self):
        if (self.debit > 0) == (self.credit > 0):
            raise ValidationError("هر ردیف فقط باید بدهکار یا بستانکار باشد.")
