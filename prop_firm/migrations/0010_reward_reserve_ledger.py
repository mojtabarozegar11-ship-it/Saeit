from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0009_plan1_invoice_gateway"),
    ]

    operations = [
        migrations.AddField(
            model_name="propplan1invoice",
            name="purchase_kind",
            field=models.CharField(
                choices=[("first", "First purchase"), ("retry", "Eligible retry purchase")],
                default="first",
                max_length=8,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="tronsettlementledger",
            name="mp_tron_plan1_amount_exact",
        ),
        migrations.AddConstraint(
            model_name="tronsettlementledger",
            constraint=models.CheckConstraint(
                condition=models.Q(amount_sun__in=[18000000, 30000000]),
                name="mp_tron_plan1_amount_exact",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="propplan1invoice",
            name="mp_plan1_invoice_amount_exact",
        ),
        migrations.AddConstraint(
            model_name="propplan1invoice",
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(purchase_kind="first") & models.Q(amount_sun=30000000))
                    | (models.Q(purchase_kind="retry") & models.Q(amount_sun=18000000))
                ),
                name="mp_plan1_invoice_amount_exact",
            ),
        ),
        migrations.CreateModel(
            name="PropRewardReserveAllocation",
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
                ("fee_sun", models.PositiveBigIntegerField()),
                ("reward_reserve_sun", models.PositiveBigIntegerField()),
                ("refund_reserve_sun", models.PositiveBigIntegerField()),
                ("operating_buffer_sun", models.PositiveBigIntegerField()),
                ("committed_reward_sun", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "invoice",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reward_reserve",
                        to="prop_firm.propplan1invoice",
                    ),
                ),
                (
                    "settlement",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reward_reserve",
                        to="prop_firm.tronsettlementledger",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="proprewardreserveallocation",
            constraint=models.CheckConstraint(
                condition=models.Q(fee_sun__in=[18000000, 30000000]),
                name="mp_reward_fee_supported",
            ),
        ),
        migrations.AddConstraint(
            model_name="proprewardreserveallocation",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(reward_reserve_sun__gt=0)
                    & models.Q(refund_reserve_sun__gte=0)
                    & models.Q(operating_buffer_sun__gte=0)
                    & models.Q(committed_reward_sun__gte=0)
                ),
                name="mp_reward_reserve_nonnegative",
            ),
        ),
        migrations.CreateModel(
            name="PropRewardCommitment",
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
                ("commitment_ref", models.CharField(max_length=96, unique=True)),
                ("amount_sun", models.PositiveBigIntegerField()),
                ("status", models.CharField(default="committed", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "allocation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="commitments",
                        to="prop_firm.proprewardreserveallocation",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="proprewardcommitment",
            constraint=models.CheckConstraint(
                condition=models.Q(amount_sun__gt=0),
                name="mp_reward_commitment_positive",
            ),
        ),
        migrations.AddIndex(
            model_name="proprewardcommitment",
            index=models.Index(
                fields=["allocation", "-created_at"],
                name="mp_reward_alloc_created",
            ),
        ),
    ]
