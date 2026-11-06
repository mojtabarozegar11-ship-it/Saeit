from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="City",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=40)),
                ("name", models.CharField(max_length=96)),
                ("biome", models.CharField(choices=[("MEADOW", "Meadow"), ("COAST", "Coast"), ("DESERT", "Desert"), ("TUNDRA", "Tundra"), ("FOREST", "Forest"), ("HIGHLAND", "Highland")], default="MEADOW", max_length=16)),
                ("level", models.PositiveIntegerField(default=1)),
                ("population", models.PositiveIntegerField(default=100)),
                ("last_harvest_at", models.DateTimeField(auto_now_add=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="living_cities", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Realm",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveBigIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("active_city", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="living_cities.city")),
                ("owner", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="living_realm", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Stock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("WOOD", "Wood"), ("FOOD", "Food"), ("STONE", "Stone"), ("CRYSTAL", "Crystal")], max_length=12)),
                ("amount", models.PositiveBigIntegerField(default=0)),
                ("capacity", models.PositiveBigIntegerField(default=10000)),
                ("city", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stocks", to="living_cities.city")),
            ],
        ),
        migrations.CreateModel(
            name="MigrationReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("idempotency_key", models.CharField(max_length=96)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("from_city", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="living_cities.city")),
                ("to_city", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="living_cities.city")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ManufactureOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_ref", models.CharField(max_length=160, unique=True)),
                ("order_evidence", models.CharField(max_length=240)),
                ("sku", models.CharField(max_length=96)),
                ("quantity", models.PositiveIntegerField()),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("issued_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="PhysicalUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_ref", models.CharField(max_length=160)),
                ("order_evidence", models.CharField(max_length=240)),
                ("sku", models.CharField(max_length=96)),
                ("serial", models.CharField(max_length=64, unique=True)),
                ("secret_digest", models.CharField(max_length=64, unique=True)),
                ("status", models.CharField(choices=[("PRINTED", "Printed"), ("DELIVERED", "Delivered"), ("CLAIMED", "Claimed"), ("VOIDED", "Voided"), ("QUARANTINED", "Quarantined")], default="PRINTED", max_length=16)),
                ("delivery_evidence", models.CharField(blank=True, max_length=240)),
                ("printed_at", models.DateTimeField(auto_now_add=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="AdultEligibility",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("adult_verified", models.BooleanField(default=False)),
                ("jurisdiction_allowed", models.BooleanField(default=False)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("owner", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="lc_crypto_eligibility", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="PhysicalCodeClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("PENDING_POLICY", "Pending policy"), ("FROZEN", "Frozen"), ("REJECTED", "Rejected")], default="PENDING_POLICY", max_length=20)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("claimant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("unit", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="claim", to="living_cities.physicalunit")),
            ],
        ),
        migrations.AddConstraint(model_name="city", constraint=models.UniqueConstraint(fields=("owner", "code"), name="lc_city_owner_code")),
        migrations.AddConstraint(model_name="stock", constraint=models.UniqueConstraint(fields=("city", "kind"), name="lc_stock_city_kind")),
        migrations.AddConstraint(model_name="migrationreceipt", constraint=models.UniqueConstraint(fields=("owner", "idempotency_key"), name="lc_migration_once")),
        migrations.AddConstraint(model_name="physicalunit", constraint=models.UniqueConstraint(fields=("order_ref", "serial"), name="lc_order_unit_unique")),
    ]
