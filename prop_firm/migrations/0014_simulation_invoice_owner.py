from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0013_restore_legacy_account_default"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="PropSimulationInvoiceOwner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("invoice", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="simulation_owner", to="prop_firm.propplan1invoice")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="prop_simulation_invoices", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
