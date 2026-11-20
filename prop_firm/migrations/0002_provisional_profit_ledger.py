"""Create provisional Moj Prop 70/30 allocation memo; no wallet/bank settlement."""
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="PropProfitAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("period_number", models.PositiveIntegerField()),
                ("start_at", models.DateTimeField()),
                ("end_at", models.DateTimeField()),
                ("cumulative_realized_net_usd",
                 models.DecimalField(max_digits=18, decimal_places=4)),
                ("previously_allocated_usd",
                 models.DecimalField(max_digits=18, decimal_places=2)),
                ("eligible_profit_usd",
                 models.DecimalField(max_digits=18, decimal_places=2)),
                ("trader_profit_usd",
                 models.DecimalField(max_digits=18, decimal_places=2)),
                ("company_profit_usd",
                 models.DecimalField(max_digits=18, decimal_places=2)),
                ("evidence_digest", models.CharField(max_length=64)),
                ("policy_version", models.CharField(
                    default="2026-11-14/v1.1", max_length=32)),
                ("status", models.CharField(
                    choices=[("provisional", "Provisional — not payable")],
                    default="provisional", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="profit_allocations", to="prop_firm.propaccount")),
            ],
            options={"ordering": ["account_id", "period_number"]},
        ),
        migrations.CreateModel(
            name="PropProfitJournalLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=16, choices=[
                    ("pool_debit", "Provisional pool debit"),
                    ("trader_credit", "Trader share provisional credit"),
                    ("company_credit", "Company share provisional credit"),
                ])),
                ("side", models.CharField(max_length=6, choices=[
                    ("debit", "Debit"), ("credit", "Credit"),
                ])),
                ("amount_usd", models.DecimalField(max_digits=18, decimal_places=2)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("allocation", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="journal_lines", to="prop_firm.propprofitallocation")),
            ],
        ),
        migrations.AddConstraint(
            model_name="propprofitallocation",
            constraint=models.UniqueConstraint(
                fields=("account", "period_number"),
                name="mp_profit_account_period_unique"),
        ),
        migrations.AddConstraint(
            model_name="propprofitallocation",
            constraint=models.CheckConstraint(
                condition=Q(period_number__gte=1),
                name="mp_profit_period_positive"),
        ),
        migrations.AddConstraint(
            model_name="propprofitallocation",
            constraint=models.CheckConstraint(
                condition=Q(previously_allocated_usd__gte=0),
                name="mp_profit_previous_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="propprofitallocation",
            constraint=models.CheckConstraint(
                condition=Q(eligible_profit_usd__gte=0),
                name="mp_profit_eligible_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="propprofitallocation",
            constraint=models.CheckConstraint(
                condition=Q(trader_profit_usd__gte=0),
                name="mp_profit_trader_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="propprofitallocation",
            constraint=models.CheckConstraint(
                condition=Q(company_profit_usd__gte=0),
                name="mp_profit_company_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="propprofitjournalline",
            constraint=models.UniqueConstraint(
                fields=("allocation", "code"),
                name="mp_profit_line_code_unique"),
        ),
        migrations.AddConstraint(
            model_name="propprofitjournalline",
            constraint=models.CheckConstraint(
                condition=Q(amount_usd__gt=0),
                name="mp_profit_line_positive"),
        ),
    ]
