from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PropSimulationIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(default="email", max_length=32)),
                ("subject_key", models.CharField(max_length=160)),
                ("email_digest", models.CharField(max_length=64)),
                ("status", models.CharField(
                    choices=[("active", "Active"), ("blocked", "Blocked"), ("pending", "Pending verification")],
                    default="pending", max_length=16,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["provider", "subject_key"], name="mp_sim_identity_subject"),
                    models.Index(fields=["status", "-created_at"], name="mp_sim_identity_status"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("provider", "subject_key"), name="mp_sim_identity_provider_subject"),
                    models.UniqueConstraint(fields=("email_digest",), name="mp_sim_identity_email_digest"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PropSimulationInvoiceOwner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invoice_ref", models.CharField(max_length=96, unique=True)),
                ("buyer_email_digest", models.CharField(max_length=64)),
                ("settlement_reference", models.CharField(blank=True, max_length=128)),
                ("settlement_verified", models.BooleanField(default=False)),
                ("contract_version", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("identity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoice_owners", to="prop_firm.propsimulationidentity")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["identity", "-created_at"], name="mp_sim_owner_identity"),
                    models.Index(fields=["settlement_verified", "-created_at"], name="mp_sim_owner_settled"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PropSimulationAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("account_ref", models.CharField(max_length=96, unique=True)),
                ("kind", models.CharField(choices=[("challenge", "Challenge simulation"), ("funded_simulation", "Funded-account simulation")], max_length=24)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("active", "Active"), ("passed", "Passed"), ("breached", "Breached"), ("closed", "Closed")], default="pending", max_length=16)),
                ("starting_capital_usd", models.DecimalField(decimal_places=2, default=1000, max_digits=18)),
                ("policy_version", models.CharField(default="2026-11-19/simulation-v1", max_length=32)),
                ("opened_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("identity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="simulation_accounts", to="prop_firm.propsimulationidentity")),
                ("invoice_owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="simulation_accounts", to="prop_firm.prosimulationinvoiceowner")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["identity", "-created_at"], name="mp_sim_account_identity"),
                    models.Index(fields=["kind", "status"], name="mp_sim_account_kind_status"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("starting_capital_usd__gt", 0)), name="mp_sim_account_capital_positive"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PropSimulationLoginChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("challenge_ref", models.CharField(max_length=96, unique=True)),
                ("purpose", models.CharField(choices=[("login", "Login"), ("recovery", "Recovery")], max_length=16)),
                ("code_digest", models.CharField(max_length=128)),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("identity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="login_challenges", to="prop_firm.prosimulationidentity")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["identity", "-created_at"], name="mp_sim_login_identity"),
                    models.Index(fields=["expires_at", "consumed_at"], name="mp_sim_login_expiry"),
                ],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("attempt_count__gte", 0)), name="mp_sim_login_attempts_nonnegative"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PropSimulationEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_ref", models.CharField(max_length=160)),
                ("sequence_no", models.PositiveBigIntegerField()),
                ("event_type", models.CharField(choices=[("equity", "Equity mark"), ("execution", "Execution"), ("risk", "Risk observation"), ("status", "Status transition")], max_length=16)),
                ("source", models.CharField(max_length=64)),
                ("occurred_at", models.DateTimeField(db_index=True)),
                ("payload_digest", models.CharField(max_length=64)),
                ("payload", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="events", to="prop_firm.prosimulationaccount")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["account", "-occurred_at"], name="mp_sim_event_account_time"),
                    models.Index(fields=["event_type", "-created_at"], name="mp_sim_event_type_created"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("account", "event_ref"), name="mp_sim_event_account_ref"),
                    models.UniqueConstraint(fields=("account", "sequence_no"), name="mp_sim_event_account_sequence"),
                ],
            },
        ),
    ]
