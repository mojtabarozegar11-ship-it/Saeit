import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0014_simulation_invoice_owner"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name="PropSimulationIdentity", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("email", models.EmailField(max_length=254, unique=True)),
            ("verified_at", models.DateTimeField()),
            ("owner", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="prop_simulation_identity", to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="PropSimulationLoginChallenge", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("email", models.EmailField(max_length=254, unique=True)),
            ("challenge_id", models.UUIDField(default=uuid.uuid4, unique=True)),
            ("code_digest", models.CharField(max_length=64)),
            ("expires_at", models.DateTimeField()),
            ("sent_at", models.DateTimeField()),
            ("attempts", models.PositiveSmallIntegerField(default=0)),
            ("consumed", models.BooleanField(default=False)),
        ]),
    ]
