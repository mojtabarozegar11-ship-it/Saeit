from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("mpw_commerce", "0002_buyerwalletchallenge_commerceorderrequest"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommerceBuyerIdentity",
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
                ("email_address", models.EmailField(blank=True, max_length=254)),
                ("email_digest", models.CharField(blank=True, max_length=64)),
                ("payer_wallet", models.CharField(blank=True, max_length=100)),
                ("network", models.CharField(blank=True, max_length=32)),
                ("tx_hash", models.CharField(blank=True, max_length=80)),
                ("source", models.CharField(blank=True, max_length=32)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="buyer_identity",
                        to="core.order",
                    ),
                ),
            ],
            options={
                "verbose_name": "Commerce buyer identity",
                "verbose_name_plural": "Commerce buyer identities",
            },
        ),
    ]
