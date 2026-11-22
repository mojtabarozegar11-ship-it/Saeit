from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0007_alter_propsimulationaccount_policy_version"),
    ]

    operations = [
        migrations.AddField(
            model_name="propsimulationaccount",
            name="tier_index",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddConstraint(
            model_name="propsimulationaccount",
            constraint=models.CheckConstraint(
                condition=models.Q(("tier_index__gte", 0))
                & models.Q(("tier_index__lte", 13)),
                name="mp_sim_account_tier_range",
            ),
        ),
        migrations.CreateModel(
            name="PropSimulationStageTransition",
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
                ("transition_key", models.CharField(max_length=96)),
                ("from_tier", models.PositiveSmallIntegerField()),
                ("to_tier", models.PositiveSmallIntegerField()),
                (
                    "from_capital_usd",
                    models.DecimalField(decimal_places=2, max_digits=18),
                ),
                (
                    "to_capital_usd",
                    models.DecimalField(decimal_places=2, max_digits=18),
                ),
                ("policy_version", models.CharField(max_length=32)),
                (
                    "performance_evidence_digest",
                    models.CharField(max_length=64),
                ),
                ("capacity_evidence_digest", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stage_transitions",
                        to="prop_firm.propsimulationaccount",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["account", "-created_at"],
                        name="mp_sim_stage_account_time",
                    ),
                    models.Index(
                        fields=["policy_version", "-created_at"],
                        name="mp_sim_stage_policy_time",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("account", "transition_key"),
                        name="mp_sim_stage_account_key",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(("from_tier__gte", 0))
                            & models.Q(("from_tier__lte", 12))
                            & models.Q(("to_tier__gte", 1))
                            & models.Q(("to_tier__lte", 13))
                        ),
                        name="mp_sim_stage_tier_range",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(("from_capital_usd__gt", 0))
                            & models.Q(("to_capital_usd__gt", 0))
                        ),
                        name="mp_sim_stage_capital_positive",
                    ),
                ],
            },
        ),
    ]
