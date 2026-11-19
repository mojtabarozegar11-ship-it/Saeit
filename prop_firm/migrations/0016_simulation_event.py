from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0015_simulation_identity")]
    operations = [
        migrations.CreateModel(name="PropSimulationEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("sequence", models.PositiveBigIntegerField()),
            ("command_id", models.UUIDField()),
            ("payload", models.JSONField()),
            ("prior_digest", models.CharField(max_length=64)),
            ("digest", models.CharField(max_length=64)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="execution_events", to="prop_firm.propsimulationaccount")),
        ], options={"ordering": ("sequence",), "constraints": [
            models.UniqueConstraint(fields=("account", "sequence"), name="mp_sim_event_sequence_unique"),
            models.UniqueConstraint(fields=("account", "command_id"), name="mp_sim_command_unique"),
        ]}),
    ]
