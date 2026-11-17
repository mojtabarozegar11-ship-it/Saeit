"""CREATE-ONLY isolated MOJ-PROP-01 v1.4.1 per-user DEMO books.

DO NOT APPLY on production without owner case approval, recoverable off-host
backup, actual MariaDB migration/rollback/concurrency rehearsal, storage check
and independent lawful onboarding. No legacy v1.2 table is altered.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("prop_firm", "0009_v141_sim_replay_journal"),
    ]
    operations = [
        migrations.CreateModel(
            name="PropV141VirtualBook",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("trader_ref", models.CharField(max_length=96)),
                ("terms_sha256", models.CharField(max_length=64)),
                ("trusted_feed_source", models.CharField(max_length=160)),
                ("evaluation_started_at", models.DateTimeField()),
                ("max_unlocked_stage", models.PositiveSmallIntegerField(default=1)),
                ("last_sequence", models.PositiveBigIntegerField(default=0)),
                ("last_history_sha256", models.CharField(max_length=64, blank=True)),
                ("last_realized_net_usd", models.DecimalField(
                    max_digits=24, decimal_places=8, default=0)),
                ("last_fully_closed_count", models.PositiveBigIntegerField(default=0)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("state", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="private_virtual_trade_book",
                    to="prop_firm.propv141simstate")),
                ("owner", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="mojprop_v141_virtual_books",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(
                    fields=["owner", "-opened_at"],
                    name="mp_v141_virtual_owner")],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(max_unlocked_stage__gte=1)
                        & models.Q(max_unlocked_stage__lte=2),
                        name="mp_v141_virt_stage_range"),
                    models.CheckConstraint(
                        condition=models.Q(last_sequence__gte=0),
                        name="mp_v141_virt_seq_nonneg"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PropV141VirtualFill",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveBigIntegerField()),
                ("event_id", models.CharField(max_length=96, unique=True)),
                ("position_ref", models.CharField(max_length=96)),
                ("stage", models.PositiveSmallIntegerField()),
                ("action", models.CharField(max_length=5)),
                ("direction", models.CharField(max_length=4)),
                ("symbol", models.CharField(max_length=10)),
                ("quantity_ounces", models.DecimalField(
                    max_digits=15, decimal_places=4)),
                ("price_usd_per_ounce", models.DecimalField(
                    max_digits=18, decimal_places=4)),
                ("fee_usd", models.DecimalField(
                    max_digits=16, decimal_places=4)),
                ("executed_at_utc", models.DateTimeField()),
                ("feed_source", models.CharField(max_length=160)),
                ("raw_event_sha256", models.CharField(max_length=64)),
                ("stored_at", models.DateTimeField(auto_now_add=True)),
                ("book", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="virtual_fills",
                    to="prop_firm.propv141virtualbook")),
            ],
            options={
                "ordering": ["book_id", "sequence"],
                "indexes": [models.Index(
                    fields=["book", "-stored_at"], name="mp_v141_virt_recent")],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["book", "sequence"],
                        name="mp_v141_virt_book_seq"),
                    models.CheckConstraint(
                        condition=models.Q(sequence__gte=1),
                        name="mp_v141_virt_event_seq_pos"),
                    models.CheckConstraint(
                        condition=models.Q(stage__gte=1)
                        & models.Q(stage__lte=2),
                        name="mp_v141_virt_event_stage"),
                    models.CheckConstraint(
                        condition=models.Q(quantity_ounces__gt=0),
                        name="mp_v141_virt_positive_qty"),
                    models.CheckConstraint(
                        condition=models.Q(price_usd_per_ounce__gt=0),
                        name="mp_v141_virt_positive_price"),
                    models.CheckConstraint(
                        condition=models.Q(fee_usd__gte=0),
                        name="mp_v141_virt_nonneg_fee"),
                ],
            },
        ),
    ]
