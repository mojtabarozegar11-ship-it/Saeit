from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("prop_firm", "0003_payment_table_router_alignment"),
    ]

    operations = [
        migrations.CreateModel(
            name="PropSimulationPayoutCommitment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "realized_profit_usd",
                    models.DecimalField(decimal_places=2, max_digits=18),
                ),
                (
                    "trader_payout_usd",
                    models.DecimalField(decimal_places=2, max_digits=18),
                ),
                (
                    "payout_percent",
                    models.PositiveSmallIntegerField(default=100),
                ),
                ("verification_ref", models.CharField(max_length=128, unique=True)),
                ("beneficiary_digest", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending_settlement", "Pending treasury settlement"),
                            ("settled", "Settled"),
                            ("blocked", "Blocked"),
                            ("disputed", "Disputed"),
                        ],
                        default="pending_settlement",
                        max_length=24,
                    ),
                ),
                ("settlement_reference", models.CharField(blank=True, max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("settled_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payout_commitment",
                        to="prop_firm.propsimulationaccount",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("realized_profit_usd__gt", 0)),
                        name="mp_sim_payout_profit_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("trader_payout_usd__gt", 0)),
                        name="mp_sim_payout_amount_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("payout_percent", 100)),
                        name="mp_sim_payout_exactly_full",
                    ),
                ],
                "indexes": [
                    models.Index(
                        fields=["status", "-created_at"],
                        name="mp_sim_payout_status",
                    ),
                    models.Index(
                        fields=["account", "-created_at"],
                        name="mp_sim_payout_account",
                    ),
                ],
            },
        ),
    ]
