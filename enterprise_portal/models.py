"""Private company ledger, trade, production and office records.

Posted journal entries and confirmed stock transactions are irreversible through
the normal ORM; corrections must use *new* reversing entries. Never aggregate
amounts in different currencies.
"""
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

AMOUNT_MIN = Decimal("0.01")
QTY_MIN = Decimal("0.001")
CURRENCIES = (
    ("IRR", "ریال"), ("USD", "دلار آمریکا"), ("EUR", "یورو"),
    ("AED", "درهم"), ("TRY", "لیر"), ("CAD", "دلار کانادا"),
)


class Stamp(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BusinessUnit(Stamp):
    code = models.SlugField(max_length=32, unique=True)
    name = models.CharField(max_length=180)
    sector = models.CharField(max_length=24, choices=(
        ("headquarters", "دفتر مرکزی"), ("agriculture", "کشاورزی"),
        ("industry", "صنعت"), ("trade", "بازرگانی"), ("services", "خدمات"),
    ), default="headquarters")
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "واحد تجاری/صنعتی"
        verbose_name_plural = "واحدهای شرکت"
        ordering = ("code",)

    def __str__(self):
        return f"{self.code} — {self.name}"


class LedgerAccount(Stamp):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT, related_name="accounts")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=12, choices=(
        ("asset", "دارایی"), ("liability", "بدهی"), ("equity", "حقوق مالکانه"),
        ("income", "درآمد"), ("expense", "هزینه"),
    ))
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "code"), name="zm_erp_unique_account_code")]
        verbose_name = "حساب دفتر کل"
        verbose_name_plural = "کدینگ و حساب‌های دفتر کل"

    def __str__(self):
        return f"{self.unit.code}/{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.get(pk=self.pk)
            used_in_posted_journal = JournalLine.objects.filter(
                account_id=self.pk, entry__status="posted"
            ).exists()
            if used_in_posted_journal and (self.unit_id, self.code, self.category) != (
                previous.unit_id, previous.code, previous.category
            ):
                raise ValidationError(
                    "کد و طبقه‌بندی حساب دارای سند قطعی قابل تغییر نیست."
                )
        return super().save(*args, **kwargs)


class JournalEntry(Stamp):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT, related_name="journals")
    reference = models.CharField(max_length=64)
    booked_on = models.DateField(default=timezone.localdate)
    description = models.CharField(max_length=320)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="IRR")
    status = models.CharField(max_length=10, choices=(("draft", "پیش‌نویس"), ("posted", "قطعی")), default="draft", editable=False)
    posted_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="zm_erp_journals")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "reference"), name="zm_erp_unique_journal_reference")]
        ordering = ("-booked_on", "-pk")
        verbose_name = "سند حسابداری"
        verbose_name_plural = "اسناد حسابداری"

    def __str__(self):
        return f"{self.reference} ({self.currency})"

    def save(self, *args, **kwargs):
        if self.pk:
            prev = type(self).objects.get(pk=self.pk)
            if prev.status == "posted":
                raise ValidationError("سند قطعی قابل ویرایش نیست؛ سند اصلاحی جدید ثبت کنید.")
            if self.status != "draft":
                raise ValidationError("قطعی‌سازی تنها از روش کنترل‌شده مجاز است.")
        elif self.status != "draft":
            raise ValidationError("سند تازه باید پیش‌نویس باشد.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, status="posted").exists():
            raise ValidationError("سند قطعی حذف نمی‌شود؛ سند برگشتی ثبت کنید.")
        return super().delete(*args, **kwargs)


class JournalLine(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, related_name="lines")
    account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT, related_name="journal_lines")
    debit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    memo = models.CharField(max_length=260, blank=True)

    class Meta:
        verbose_name = "آرتیکل سند"
        verbose_name_plural = "آرتیکل‌های اسناد"

    def clean(self):
        errors = {}
        if self.debit is None or self.credit is None or self.debit < 0 or self.credit < 0:
            errors["debit"] = "مبلغ بدهکار و بستانکار باید نامنفی باشد."
        elif (self.debit > 0) == (self.credit > 0):
            errors["credit"] = "هر ردیف باید دقیقاً یکی از بدهکار یا بستانکار را داشته باشد."
        if self.entry_id and JournalEntry.objects.filter(pk=self.entry_id, status="posted").exists():
            errors["entry"] = "سند قطعی قابل تغییر نیست."
        if self.account_id and self.entry_id and self.account.unit_id != self.entry.unit_id:
            errors["account"] = "حساب باید متعلق به همان واحد تجاری باشد."
        if self.account_id and not self.account.active:
            errors["account"] = "حساب غیرفعال قابل استفاده نیست."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.entry_id and JournalEntry.objects.filter(pk=self.entry_id, status="posted").exists():
            raise ValidationError("آرتیکل سند قطعی حذف نمی‌شود.")
        return super().delete(*args, **kwargs)


class Partner(Stamp):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT, related_name="partners")
    name = models.CharField(max_length=220)
    kind = models.CharField(max_length=24, choices=(
        ("customer", "مشتری"), ("supplier", "تأمین‌کننده"),
        ("both", "مشتری و تأمین‌کننده"), ("other", "سایر"),
    ), default="customer")
    tax_id = models.CharField(max_length=60, blank=True)
    contact = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "طرف تجاری"
        verbose_name_plural = "مشتریان و تأمین‌کنندگان"

    def __str__(self):
        return self.name


class CommercialDocument(Stamp):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT, related_name="trade_documents")
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="documents")
    number = models.CharField(max_length=64)
    kind = models.CharField(max_length=24, choices=(
        ("sales", "فاکتور فروش"), ("purchase", "فاکتور خرید"),
        ("quotation", "پیش‌فاکتور"), ("contract", "قرارداد"),
    ))
    issued_on = models.DateField(default=timezone.localdate)
    due_on = models.DateField(null=True, blank=True)
    total = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(AMOUNT_MIN)])
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="IRR")
    status = models.CharField(max_length=24, choices=(
        ("draft", "پیش‌نویس"), ("approved", "تأییدشده"),
        ("settled", "تسویه‌شده"), ("cancelled", "لغو شده"),
    ), default="draft")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="zm_erp_trade_docs")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "number"), name="zm_erp_unique_trade_document")]
        verbose_name = "سند خرید و فروش"
        verbose_name_plural = "فاکتورها و قراردادهای تجاری"

    def clean(self):
        if self.partner_id and self.unit_id and self.partner.unit_id != self.unit_id:
            raise ValidationError({"partner": "طرف تجاری متعلق به واحد انتخاب‌شده نیست."})

    def __str__(self):
        return f"{self.number} — {self.get_kind_display()}"


class InventoryItem(Stamp):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT, related_name="inventory")
    sku = models.CharField(max_length=64)
    title = models.CharField(max_length=240)
    measure = models.CharField(max_length=24, default="عدد")
    reorder_point = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "sku"), name="zm_erp_unique_inventory_sku")]
        verbose_name = "کالای انبار"
        verbose_name_plural = "موجودی انبار"

    def __str__(self):
        return f"{self.sku} — {self.title}"


class StockMovement(Stamp):
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    reference = models.CharField(max_length=64)
    direction = models.CharField(max_length=3, choices=(("in", "ورود"), ("out", "خروج")))
    quantity = models.DecimalField(max_digits=18, decimal_places=3, validators=[MinValueValidator(QTY_MIN)])
    note = models.CharField(max_length=320, blank=True)
    status = models.CharField(max_length=12, choices=(("draft", "پیش‌نویس"), ("confirmed", "قطعی")), default="draft", editable=False)
    confirmed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="zm_erp_stock_actions")

    class Meta:
        verbose_name = "گردش کالا"
        verbose_name_plural = "ورود و خروج انبار"

    def save(self, *args, **kwargs):
        if self.pk:
            prev = type(self).objects.get(pk=self.pk)
            if prev.status != "draft" or self.status != "draft":
                raise ValidationError("گردش قطعی تغییر نمی‌کند؛ اصلاح با گردش جدید انجام شود.")
        elif self.status != "draft":
            raise ValidationError("گردش جدید ابتدا پیش‌نویس است.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, status="confirmed").exists():
            raise ValidationError("گردش قطعی حذف نمی‌شود.")
        return super().delete(*args, **kwargs)


class OfficeLetter(Stamp):
    number = models.CharField(max_length=64, unique=True)
    subject = models.CharField(max_length=260)
    direction = models.CharField(max_length=16, choices=(
        ("incoming", "وارده"), ("outgoing", "صادره"), ("internal", "داخلی"),
    ))
    body = models.TextField()
    classification = models.CharField(max_length=16, choices=(
        ("normal", "عادی"), ("confidential", "محرمانه"),
    ), default="normal")
    sent_on = models.DateField(default=timezone.localdate)
    recipient = models.CharField(max_length=180, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="zm_erp_assigned_letters")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="zm_erp_created_letters")

    class Meta:
        permissions = [("view_confidential_letters", "مشاهده مکاتبات محرمانه")]
        verbose_name = "نامه اداری"
        verbose_name_plural = "دبیرخانه و مکاتبات"


class WorkTask(Stamp):
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT, null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="zm_erp_work_tasks")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="zm_erp_issued_tasks")
    priority = models.CharField(max_length=12, choices=(
        ("normal", "عادی"), ("high", "مهم"), ("urgent", "فوری"),
    ), default="normal")
    status = models.CharField(max_length=16, choices=(
        ("todo", "در انتظار"), ("doing", "در انجام"),
        ("review", "بازبینی"), ("done", "انجام‌شده"),
    ), default="todo")
    due_on = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "کار سازمانی"
        verbose_name_plural = "وظایف و پیگیری‌ها"


class Meeting(Stamp):
    title = models.CharField(max_length=220)
    agenda = models.TextField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    location = models.CharField(max_length=180, blank=True)
    minutes = models.TextField(blank=True)
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    attendees = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="zm_erp_meetings")

    class Meta:
        verbose_name = "جلسه"
        verbose_name_plural = "تقویم جلسات و صورت‌جلسات"

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "پایان جلسه باید بعد از زمان شروع باشد."})


class ManagementProject(Stamp):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    code = models.CharField(max_length=48)
    title = models.CharField(max_length=240)
    objective = models.TextField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    planned_start = models.DateField(null=True, blank=True)
    planned_finish = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=(
        ("idea", "در دست مطالعه"), ("approved", "مصوب"),
        ("active", "در اجرا"), ("closed", "مختومه"),
    ), default="idea")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "code"), name="zm_erp_unique_management_project")]
        verbose_name = "طرح مدیریتی"
        verbose_name_plural = "پروژه‌ها و برنامه‌های مدیریت"

    def clean(self):
        if self.planned_start and self.planned_finish and self.planned_finish < self.planned_start:
            raise ValidationError({"planned_finish": "پایان پروژه نمی‌تواند پیش از آغاز باشد."})


class BudgetPlan(Stamp):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    project = models.ForeignKey(ManagementProject, on_delete=models.PROTECT, null=True, blank=True)
    fiscal_year = models.PositiveIntegerField()
    title = models.CharField(max_length=240)
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="IRR")
    amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(AMOUNT_MIN)])
    status = models.CharField(max_length=12, choices=(
        ("draft", "پیشنهادی"), ("approved", "مصوب"),
    ), default="draft")

    class Meta:
        verbose_name = "بودجه"
        verbose_name_plural = "بودجه‌ها و برنامه مالی"

    def clean(self):
        if self.project_id and self.unit_id and self.project.unit_id != self.unit_id:
            raise ValidationError({"project": "پروژه و واحد باید یکسان باشند."})


class CompanyAsset(Stamp):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    code = models.CharField(max_length=48)
    title = models.CharField(max_length=220)
    acquired_on = models.DateField()
    purchase_cost = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(AMOUNT_MIN)])
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="IRR")
    custodian = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    location = models.CharField(max_length=160, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "code"), name="zm_erp_unique_fixed_asset")]
        verbose_name = "دارایی ثابت"
        verbose_name_plural = "اموال و دارایی‌های ثابت"


class AuditEvent(models.Model):
    occurred_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    target = models.CharField(max_length=160)
    detail = models.JSONField(default=dict)

    class Meta:
        verbose_name = "رخداد حسابرسی"
        verbose_name_plural = "سوابق کنترل و حسابرسی"
        ordering = ("-occurred_at",)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("ردیف سوابق حسابرسی قابل ویرایش نیست.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("سوابق حسابرسی حذف نمی‌شود.")
