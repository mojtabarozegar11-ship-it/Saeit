# Moj Prop schema v1.0 — authoring source only; subject to Django migration CI.
import decimal
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PropTrader",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("preferred_language", models.CharField(default="en", max_length=8)),
                ("kyc_status", models.CharField(
                    choices=[("not_started", "Not started"), ("pending", "Pending review"),
                             ("verified", "Verified"), ("rejected", "Rejected")],
                    default="not_started", max_length=16)),
                ("eligibility_status", models.CharField(
                    choices=[("not_reviewed", "Not reviewed"), ("eligible", "Eligible"),
                             ("blocked", "Blocked")],
                    default="not_reviewed", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                                              related_name="moj_prop_trader",
                                              to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PropAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[
                    ("phase_one", "Challenge stage one (simulation)"),
                    ("phase_two", "Challenge stage two (simulation)"),
                    ("funded", "Company-funded real brokerage"),
                ], max_length=20)),
                ("status", models.CharField(choices=[
                    ("waiting", "Awaiting evidence"),
                    ("active", "Reconciliation in progress"),
                    ("passed", "Assessment passed"),
                    ("breached", "Risk breach"),
                    ("closed", "Closed"),
                ], default="waiting", max_length=16)),
                ("tier_index", models.PositiveSmallIntegerField(default=0)),
                ("starting_capital_usd", models.DecimalField(
                    decimal_places=2, default=decimal.Decimal("100.00"), max_digits=18)),
                ("reference", models.CharField(blank=True, max_length=96)),
                ("policy_version", models.CharField(default="2026-11-14/v1.1", max_length=32)),
                ("reconciled_by_operator", models.BooleanField(default=False)),
                ("opened_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("trader", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            related_name="accounts", to="prop_firm.proptrader")),
            ],
        ),
        migrations.CreateModel(
            name="PropExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_event_id", models.CharField(max_length=160)),
                ("data_source", models.CharField(max_length=64)),
                ("symbol", models.CharField(max_length=32)),
                ("closed_at", models.DateTimeField(db_index=True)),
                ("gross_realized_usd", models.DecimalField(decimal_places=4, max_digits=18)),
                ("total_fees_usd", models.DecimalField(decimal_places=4,
                                                     default=decimal.Decimal("0"), max_digits=18)),
                ("reconciliation_status", models.CharField(choices=[
                    ("pending", "Pending"), ("verified", "Verified"), ("rejected", "Rejected")
                ], default="pending", max_length=12)),
                ("evidence_digest", models.CharField(blank=True, max_length=64)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             related_name="executions", to="prop_firm.propaccount")),
            ],
            options={"ordering": ["-closed_at", "-id"]},
        ),
        migrations.CreateModel(
            name="PropEquityObservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_event_id", models.CharField(max_length=160)),
                ("observed_at", models.DateTimeField(db_index=True)),
                ("equity_usd", models.DecimalField(decimal_places=4, max_digits=18)),
                ("is_session_open", models.BooleanField(default=False)),
                ("reconciliation_status", models.CharField(choices=[
                    ("pending", "Pending"), ("verified", "Verified"), ("rejected", "Rejected")
                ], default="pending", max_length=12)),
                ("evidence_digest", models.CharField(blank=True, max_length=64)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             related_name="equity_observations", to="prop_firm.propaccount")),
            ],
            options={"ordering": ["-observed_at", "-id"]},
        ),
        migrations.CreateModel(
            name="PropDecisionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("decision_key", models.CharField(max_length=96)),
                ("category", models.CharField(choices=[
                    ("challenge", "Challenge"), ("promotion", "Promotion"),
                    ("payout_preview", "Payout estimate"), ("risk", "Risk assessment"),
                ], max_length=20)),
                ("policy_version", models.CharField(default="2026-11-14/v1.1", max_length=32)),
                ("qualifies", models.BooleanField(default=False)),
                ("reasons", models.JSONField(default=list)),
                ("evidence_digest", models.CharField(max_length=64)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             related_name="decision_logs", to="prop_firm.propaccount")),
            ],
            options={"ordering": ["-recorded_at"]},
        ),
        migrations.AddIndex(model_name="propaccount",
                            index=models.Index(fields=["trader", "-created_at"],
                                               name="mp_account_trader_created")),
        migrations.AddIndex(model_name="propaccount",
                            index=models.Index(fields=["kind", "status"],
                                               name="mp_account_type_status")),
        migrations.AddIndex(model_name="propexecution",
                            index=models.Index(fields=["account", "closed_at"],
                                               name="mp_trade_account_closed")),
        migrations.AddIndex(model_name="propequityobservation",
                            index=models.Index(fields=["account", "-observed_at"],
                                               name="mp_equity_account_recent")),
        migrations.AddConstraint(model_name="propaccount", constraint=models.CheckConstraint(
            condition=models.Q(tier_index__gte=0, tier_index__lte=13), name="mp_tier_range_0_13")),
        migrations.AddConstraint(model_name="propaccount", constraint=models.CheckConstraint(
            condition=models.Q(starting_capital_usd__gt=0),
            name="mp_initial_capital_positive")),
        migrations.AddConstraint(model_name="propexecution", constraint=models.UniqueConstraint(
            fields=("account", "external_event_id"), name="mp_execution_external_unique")),
        migrations.AddConstraint(model_name="propexecution", constraint=models.CheckConstraint(
            condition=models.Q(total_fees_usd__gte=0), name="mp_execution_fees_nonnegative")),
        migrations.AddConstraint(model_name="propequityobservation", constraint=models.UniqueConstraint(
            fields=("account", "external_event_id"), name="mp_equity_event_unique")),
        migrations.AddConstraint(model_name="propequityobservation", constraint=models.CheckConstraint(
            condition=models.Q(equity_usd__gte=0), name="mp_equity_nonnegative")),
        migrations.AddConstraint(model_name="propdecisionlog", constraint=models.UniqueConstraint(
            fields=("account", "decision_key"), name="mp_decision_idempotency")),
    ]
