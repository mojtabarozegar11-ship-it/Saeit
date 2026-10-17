"""Expandable multi-unit management, production and review-only assistants.

No model creates accounting postings, real payments, stock postings or external
content. Link to the existing ERP records rather than duplicating their balances.
"""
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from enterprise_portal.models import (
    BusinessUnit, InventoryItem, ManagementProject, CompanyAsset, WorkTask,
)


POSITIVE = MinValueValidator(Decimal("0.001"))
MONEY_POSITIVE = MinValueValidator(Decimal("0.01"))


class Timeline(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(Timeline):
    """Legal entity / division. Existing BusinessUnit is the isolation key."""
    unit = models.OneToOneField(BusinessUnit, on_delete=models.PROTECT, related_name="ecosystem_identity")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    legal_name = models.CharField(max_length=240)
    is_legal_entity = models.BooleanField(default=False)
    registration_note = models.CharField(max_length=240, blank=True)
    default_currency = models.CharField(max_length=3, default="IRR")
    reporting_timezone = models.CharField(max_length=64, default="Asia/Tehran")

    class Meta:
        verbose_name = "هویت سازمانی زیرمجموعه"
        verbose_name_plural = "شرکت‌ها و واحدهای اکوسیستم"

    def clean(self):
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": "یک واحد نمی‌تواند والد خود باشد."})
            visited = {self.pk}
            node = self.parent
            while node:
                if node.pk in visited:
                    raise ValidationError({"parent": "حلقه در سلسله‌مراتب سازمانی مجاز نیست."})
                visited.add(node.pk)
                node = node.parent

    def __str__(self):
        return self.legal_name


class UnitMembership(Timeline):
    ROLE = (("owner", "مدیر ارشد"), ("manager", "مدیر واحد"),
            ("finance", "حسابدار"), ("operations", "عملیات"),
            ("analyst", "تحلیلگر"), ("viewer", "مشاهده‌گر"))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ecosystem_memberships")
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT, related_name="ecosystem_memberships")
    role = models.CharField(max_length=16, choices=ROLE, default="viewer")
    can_approve = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "unit"), name="zm_hub_one_membership_per_unit")]
        verbose_name = "دسترسی کارمند به واحد"
        verbose_name_plural = "مجوزهای واحدهای اکوسیستم"


class ManagedSite(Timeline):
    """References only. No automated network requests or write access."""
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    label = models.CharField(max_length=160)
    path = models.CharField(max_length=220, help_text="مسیر دقیق با / آغاز شود")
    owner_contact = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=18, choices=(
        ("planned", "در برنامه"), ("operating", "در حال فعالیت"), ("paused", "متوقف"),
    ), default="planned")
    last_reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "path"), name="zm_hub_site_unique_unit_path")]
        verbose_name = "سامانه زیرمجموعه"
        verbose_name_plural = "سامانه‌ها و زیرسایت‌های اکوسیستم"

    def clean(self):
        if not self.path.startswith("/") or self.path.startswith("//") or ".." in self.path:
            raise ValidationError({"path": "آدرس باید مسیر داخلی ایمن سایت باشد."})


class WorkCenter(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=180)
    nominal_hours_per_day = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("8.00"),
                                                 validators=[MinValueValidator(Decimal("0.01"))])
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "code"), name="zm_hub_unique_workcenter")]
        verbose_name = "مرکز تولید"
        verbose_name_plural = "ظرفیت و مراکز تولید"


class BillOfMaterials(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    product = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="production_recipes")
    code = models.CharField(max_length=48)
    revision = models.PositiveIntegerField(default=1)
    yield_quantity = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal("1"),
                                         validators=[POSITIVE])
    state = models.CharField(max_length=12, choices=(("draft", "پیش‌نویس"), ("reviewed", "بازبینی‌شده")), default="draft")
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "code", "revision"), name="zm_hub_unique_bom_revision")]
        verbose_name = "فرمول ساخت"
        verbose_name_plural = "فرمول‌های مواد اولیه و بهای ساخت"

    def clean(self):
        if self.product_id and self.unit_id and self.product.unit_id != self.unit_id:
            raise ValidationError({"product": "محصول نهایی باید متعلق به همین واحد باشد."})


class MaterialRequirement(models.Model):
    formula = models.ForeignKey(BillOfMaterials, on_delete=models.PROTECT, related_name="materials")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=18, decimal_places=3, validators=[POSITIVE])
    scrap_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"),
                                         validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))])

    class Meta:
        constraints = [models.UniqueConstraint(fields=("formula", "item"), name="zm_hub_unique_bom_material")]
        verbose_name = "جزء فرمول"
        verbose_name_plural = "مواد اولیه محصول"

    def clean(self):
        if self.formula_id and self.item_id:
            if self.item.unit_id != self.formula.unit_id:
                raise ValidationError({"item": "مواد اولیه باید متعلق به همان واحد تولیدی باشند."})
            if self.formula.product_id == self.item_id:
                raise ValidationError({"item": "محصول نمی‌تواند جزء مستقیم خودش باشد."})


class ProductionOrder(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    code = models.CharField(max_length=50)
    formula = models.ForeignKey(BillOfMaterials, on_delete=models.PROTECT, related_name="orders")
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, null=True, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=3, validators=[POSITIVE])
    planned_start = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    state = models.CharField(max_length=16, choices=(
        ("draft", "برنامه اولیه"), ("review", "در انتظار بررسی"),
        ("approved", "برنامه مصوب"), ("closed", "مختومه"),
        ("cancelled", "لغو شده"),
    ), default="draft")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "code"), name="zm_hub_unique_production_order")]
        verbose_name = "سفارش تولید"
        verbose_name_plural = "سفارش‌ها و برنامه تولید"

    def clean(self):
        if self.unit_id and self.formula_id and self.formula.unit_id != self.unit_id:
            raise ValidationError({"formula": "فرمول تولید متعلق به واحد انتخاب‌شده نیست."})
        if self.unit_id and self.work_center_id and self.work_center.unit_id != self.unit_id:
            raise ValidationError({"work_center": "مرکز تولید به واحد دیگری تعلق دارد."})
        if self.planned_start and self.due_date and self.due_date < self.planned_start:
            raise ValidationError({"due_date": "سررسید نباید قبل از شروع تولید باشد."})



class MaterialPriceReference(Timeline):
    """Manually researched price; no inferred rates or external purchases."""
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="price_references")
    currency = models.CharField(max_length=3, choices=(
        ("IRR", "ریال"), ("USD", "دلار"), ("EUR", "یورو"),
        ("AED", "درهم"), ("TRY", "لیر"), ("CAD", "دلار کانادا"),
    ), default="IRR")
    amount = models.DecimalField(max_digits=20, decimal_places=4, validators=[
        MinValueValidator(Decimal("0.0001"))
    ], help_text="قیمت هر واحد اندازه‌گیری کالا")
    as_of = models.DateField(default=timezone.localdate)
    evidence_ref = models.CharField(max_length=280, blank=True)
    status = models.CharField(max_length=12, choices=(
        ("draft", "پیش‌نویس"), ("verified", "بررسی‌شده"),
    ), default="draft")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        verbose_name = "نرخ مستند ماده"
        verbose_name_plural = "نرخ‌های مستند مواد اولیه"
        ordering = ("-as_of", "-pk")

    def clean(self):
        if self.item_id and self.unit_id and self.item.unit_id != self.unit_id:
            raise ValidationError({"item": "نرخ باید به کالای همان واحد تعلق داشته باشد."})
        if self.status == "verified" and not self.evidence_ref.strip():
            raise ValidationError({"evidence_ref": "نرخ بررسی‌شده باید منبع یا سند معتبر داشته باشد."})

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, status="verified").exists():
            raise ValidationError("نرخ بررسی‌شده قفل است؛ برای اصلاح، نرخ مستند جدید ثبت کنید.")
        self.full_clean()
        return super().save(*args, **kwargs)


class ProductionCostScenario(Timeline):
    """Budgetary *estimate* tied to a production order; never posted to the GL."""
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    order = models.ForeignKey(ProductionOrder, on_delete=models.PROTECT, related_name="cost_scenarios")
    label = models.CharField(max_length=200)
    currency = models.CharField(max_length=3, choices=(
        ("IRR", "ریال"), ("USD", "دلار"), ("EUR", "یورو"),
        ("AED", "درهم"), ("TRY", "لیر"), ("CAD", "دلار کانادا"),
    ), default="IRR")
    labor_estimate = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"),
                                         validators=[MinValueValidator(Decimal("0"))])
    overhead_estimate = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"),
                                            validators=[MinValueValidator(Decimal("0"))])
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "سناریوی بهای تولید"
        verbose_name_plural = "برآورد بهای تمام‌شده تولید"

    def clean(self):
        if self.unit_id and self.order_id and self.order.unit_id != self.unit_id:
            raise ValidationError({"order": "سفارش تولید و سناریوی هزینه باید متعلق به یک واحد باشند."})


class ProcurementNeed(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    reference = models.CharField(max_length=50)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=18, decimal_places=3, validators=[POSITIVE])
    request_reason = models.CharField(max_length=350)
    required_by = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=(
        ("draft", "پیشنویس"), ("review", "بررسی"), ("approved", "تصویب شده"),
        ("cancelled", "لغو شده"),
    ), default="draft")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "reference"), name="zm_hub_unique_procurement")]
        verbose_name = "نیاز خرید"
        verbose_name_plural = "درخواست‌های تأمین و تدارکات"

    def clean(self):
        if self.item_id and self.unit_id and self.item.unit_id != self.unit_id:
            raise ValidationError({"item": "قلم خرید باید به واحد درخواست‌کننده تعلق داشته باشد."})


class QualityInspection(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    order = models.ForeignKey(ProductionOrder, on_delete=models.PROTECT, null=True, blank=True)
    sample_ref = models.CharField(max_length=80)
    title = models.CharField(max_length=220)
    result = models.CharField(max_length=12, choices=(
        ("pending", "در انتظار"), ("pass", "قبول"), ("fail", "رد"), ("hold", "قرنطینه"),
    ), default="pending")
    evidence = models.TextField(blank=True)
    inspected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    inspected_on = models.DateField(default=timezone.localdate)

    class Meta:
        verbose_name = "بازرسی کیفیت"
        verbose_name_plural = "کنترل کیفیت و محصول"

    def clean(self):
        if self.unit_id and self.order_id and self.order.unit_id != self.unit_id:
            raise ValidationError({"order": "بازرسی به سفارش تولید همان واحد تعلق دارد."})


class MaintenanceTicket(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    asset = models.ForeignKey(CompanyAsset, on_delete=models.PROTECT)
    title = models.CharField(max_length=230)
    due_date = models.DateField()
    priority = models.CharField(max_length=12, choices=(
        ("normal", "عادی"), ("high", "بالا"), ("urgent", "فوری"),
    ), default="normal")
    status = models.CharField(max_length=12, choices=(
        ("open", "باز"), ("doing", "در حال انجام"), ("done", "بسته"),
    ), default="open")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        verbose_name = "تعمیرات و نگهداری"
        verbose_name_plural = "نگهداری پیشگیرانه تجهیزات"

    def clean(self):
        if self.unit_id and self.asset_id and self.asset.unit_id != self.unit_id:
            raise ValidationError({"asset": "دارایی و برنامه نگهداری باید یک واحد داشته باشند."})


class StaffAssignment(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=180)
    starts_on = models.DateField(default=timezone.localdate)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "person", "title"), name="zm_hub_unique_staff_position")]
        verbose_name = "سمت سازمانی"
        verbose_name_plural = "منابع انسانی و سمت‌ها"


class Timesheet(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    project = models.ForeignKey(ManagementProject, on_delete=models.PROTECT, null=True, blank=True)
    work_date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2,
                                validators=[MinValueValidator(Decimal("0.25")), MaxValueValidator(Decimal("24"))])
    approved = models.BooleanField(default=False)
    description = models.CharField(max_length=320, blank=True)

    class Meta:
        verbose_name = "برگه کارکرد"
        verbose_name_plural = "کارکرد و مدیریت نیروی انسانی"

    def clean(self):
        if self.project_id and self.unit_id and self.project.unit_id != self.unit_id:
            raise ValidationError({"project": "پروژه و کارکرد باید به یک واحد تعلق داشته باشند."})


class ManagementRisk(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    title = models.CharField(max_length=240)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    likelihood = models.PositiveSmallIntegerField(default=1, validators=[
        MinValueValidator(1), MaxValueValidator(5)])
    impact = models.PositiveSmallIntegerField(default=1, validators=[
        MinValueValidator(1), MaxValueValidator(5)])
    mitigation = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    state = models.CharField(max_length=12, choices=(
        ("open", "باز"), ("mitigating", "در حال کنترل"), ("closed", "بسته"),
    ), default="open")

    class Meta:
        verbose_name = "ریسک مدیریتی"
        verbose_name_plural = "مدیریت ریسک و انطباق"

    @property
    def risk_score(self):
        return self.likelihood * self.impact


class PerformanceIndicator(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    code = models.SlugField(max_length=60)
    label = models.CharField(max_length=200)
    period = models.CharField(max_length=24, help_text="YYYY-MM")
    measurement_unit = models.CharField(max_length=24, default="unit")
    target = models.DecimalField(max_digits=18, decimal_places=3)
    actual = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    evidence_note = models.CharField(max_length=320, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "code", "period"), name="zm_hub_unique_kpi_period")]
        verbose_name = "شاخص عملکرد"
        verbose_name_plural = "شاخص‌های عملکرد و کنترل اهداف"


class ReviewApproval(Timeline):
    """A review record, NOT a generic executor for financial transactions."""
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    summary = models.CharField(max_length=260)
    target_type = models.CharField(max_length=90)
    target_reference = models.CharField(max_length=90)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="eco_requested_approvals")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="eco_assigned_approvals")
    decision = models.CharField(max_length=12, choices=(
        ("pending", "نیازمند بررسی"), ("accepted", "تأیید پیشنهاد"),
        ("rejected", "رد پیشنهاد"),
    ), default="pending")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rationale = models.TextField(blank=True)

    class Meta:
        verbose_name = "درخواست بازبینی"
        verbose_name_plural = "صف کنترل و تأیید تصمیم‌ها"


class ReferenceEvidence(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    title = models.CharField(max_length=230)
    document_ref = models.CharField(max_length=280, help_text="شناسه سند داخلی، بدون محتوای محرمانه")
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    reviewed = models.BooleanField(default=False)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        verbose_name = "شاهد تصمیم"
        verbose_name_plural = "شواهد و اسناد پشتیبان"


class AssistantRun(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    assistant_code = models.SlugField(max_length=60)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    state = models.CharField(max_length=14, choices=(
        ("draft", "پیش‌نویس"), ("review", "در صف بررسی"),
        ("failed", "خطا"),
    ), default="draft")
    generated_at = models.DateTimeField(default=timezone.now)
    findings = models.JSONField(default=list)
    evidence = models.JSONField(default=dict)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="eco_reviewed_runs")

    class Meta:
        verbose_name = "گزارش دستیار"
        verbose_name_plural = "گزارش‌های دستیارهای هوشمند"
        ordering = ("-generated_at",)

    def save(self, *args, **kwargs):
        # Do not allow falsely asserting an assistant autonomously executed a task.
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            before = type(self).objects.get(pk=self.pk)
            if self.assistant_code != before.assistant_code or self.unit_id != before.unit_id:
                raise ValidationError("دامنه و نوع گزارش دستیار قابل جابه‌جایی نیست.")
            if self.findings != before.findings or self.evidence != before.evidence:
                raise ValidationError("یافته‌ها و شواهد گزارش پس از تولید قابل ویرایش نیستند.")
        super().save(*args, **kwargs)


class AssistantFollowUp(Timeline):
    """Human-created task for a specific assistant finding, not an automated action."""
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    report = models.ForeignKey(AssistantRun, on_delete=models.PROTECT, related_name="followups")
    finding_index = models.PositiveIntegerField()
    task = models.OneToOneField(WorkTask, on_delete=models.PROTECT, related_name="assistant_followup")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=("report", "finding_index"), name="zm_eco_unique_followup_finding")]
        verbose_name = "پیگیری یافته دستیار"
        verbose_name_plural = "پیگیری‌های انسانی دستیارها"

    def clean(self):
        errors = {}
        if self.report_id and self.unit_id and self.report.unit_id != self.unit_id:
            errors["unit"] = "گزارش و وظیفه باید متعلق به همان واحد باشند."
        if self.task_id and self.unit_id and self.task.unit_id != self.unit_id:
            errors["task"] = "وظیفه در واحد دیگری ثبت شده است."
        if self.report_id and self.finding_index is not None:
            items = self.report.findings if isinstance(self.report.findings, list) else []
            if self.finding_index >= len(items):
                errors["finding_index"] = "یافته انتخاب‌شده در گزارش وجود ندارد."
        if errors:
            raise ValidationError(errors)


class ProposedAutomation(Timeline):
    unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    assistant_code = models.SlugField(max_length=60)
    cadence = models.CharField(max_length=16, choices=(
        ("daily", "روزانه"), ("weekly", "هفتگی"), ("monthly", "ماهانه"),
    ), default="daily")
    active = models.BooleanField(default=False)
    requires_human_review = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        verbose_name = "پیشنهاد زمان‌بندی"
        verbose_name_plural = "برنامه‌های پیشنهادی دستیارها"

    def clean(self):
        if not self.requires_human_review:
            raise ValidationError({"requires_human_review": "کنترل انسانی برای اقدامات مدیریتی الزامی است."})
