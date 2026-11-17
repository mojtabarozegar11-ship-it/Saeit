"""Add isolated v1.4.1 DEMO replay state and receipts; NO data migration.

Creation only. No changes to signed v1.2 customers, broker permissions,
settlement, funds or payment. DO NOT APPLY in production until backup
restore, storage capacity and release authorization are independently proven.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0008_prospect_contact_intake")]

    operations = [
        migrations.CreateModel(
            name="PropV141SimState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("challenge_ref", models.CharField(max_length=64, unique=True)),
                ("terms_sha256", models.CharField(max_length=64)),
                ("trusted_source", models.CharField(max_length=160)),
                ("trusted_key_id", models.CharField(max_length=160)),
                ("last_sequence", models.PositiveBigIntegerField(default=0)),
                ("last_manifest_sha256", models.CharField(max_length=64, blank=True)),
                ("last_replay_sha256", models.CharField(max_length=64, blank=True)),
                ("last_as_of", models.DateTimeField(null=True, blank=True)),
                ("last_phase_one_accepted_at", models.DateTimeField(null=True, blank=True)),
                ("last_phase_one_evidence_sha256", models.CharField(max_length=64, blank=True)),
                ("last_phase_two_started_at", models.DateTimeField(null=True, blank=True)),
                ("last_phase_two_completed_at", models.DateTimeField(null=True, blank=True)),
                ("last_engine_state", models.CharField(
                    max_length=96, default="PENDING_SIGNED_SIMULATOR_FEED")),
                ("last_receipt_sha256", models.CharField(max_length=64, blank=True)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["trusted_source", "last_sequence"],
                                 name="mp_v141_source_seq"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(last_sequence__gte=0),
                                           name="mp_v141_nonnegative_seq"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PropV141SimReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveBigIntegerField()),
                ("manifest_id", models.CharField(max_length=160)),
                ("raw_manifest_sha256", models.CharField(max_length=64)),
                ("replay_sha256", models.CharField(max_length=64)),
                ("previous_receipt_sha256", models.CharField(max_length=64)),
                ("receipt_sha256", models.CharField(max_length=64)),
                ("reported_engine_state", models.CharField(max_length=96)),
                ("as_of", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("state", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="replay_receipts", to="prop_firm.propv141simstate")),
            ],
            options={
                "ordering": ["state_id", "sequence"],
                "indexes": [
                    models.Index(fields=["state", "-created_at"],
                                 name="mp_v141_recent_receipt"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=["state", "sequence"],
                                            name="mp_v141_receipt_state_seq"),
                    models.UniqueConstraint(fields=["state", "manifest_id"],
                                            name="mp_v141_receipt_unique_id"),
                    models.CheckConstraint(condition=models.Q(sequence__gte=1),
                                           name="mp_v141_receipt_positive_seq"),
                ],
            },
        ),
    ]
