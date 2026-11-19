from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0011_plan1_account_default"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="PropSimulationAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("starting_balance_usd", models.PositiveIntegerField(default=1000)),
                ("challenge_days", models.PositiveSmallIntegerField(default=60)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(default="active", max_length=16)),
                ("invoice", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="simulation_account", to="prop_firm.propplan1invoice")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="prop_simulation_accounts", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
