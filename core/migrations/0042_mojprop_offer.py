"""Commercial proposal records: never create a payment, fulfillment or email."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0041_mojprop_request"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="MojPropOffer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180)),
                ("scope", models.TextField()),
                ("exclusions", models.TextField(default="No live funded account, live trading, guaranteed returns or subscriptions.")),
                ("amount", models.DecimalField(max_digits=12, decimal_places=2)),
                ("currency", models.CharField(max_length=3, default="USD", choices=[("USD", "US dollar"), ("IRR", "Iranian rial")])),
                ("delivery_days", models.PositiveSmallIntegerField(default=7)),
                ("status", models.CharField(max_length=12, default="draft", choices=[
                    ("draft", "Draft - not issued"),
                    ("approved", "Reviewed for manual issuance"),
                    ("issued", "Manually issued - delivery not promised"),
                    ("accepted", "Acceptance recorded - not paid"),
                    ("cancelled", "Cancelled"),
                    ("expired", "Expired"),
                ])),
                ("expires_at", models.DateTimeField(null=True, blank=True)),
                ("reviewed_at", models.DateTimeField(null=True, blank=True)),
                ("issued_at", models.DateTimeField(null=True, blank=True)),
                ("internal_note", models.TextField(blank=True, default="")),
                ("created_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    related_name="mojprop_offers",
                    null=True, blank=True,
                    on_delete=django.db.models.deletion.PROTECT,
                )),
                ("lead", models.OneToOneField(
                    to="core.mojproprequest",
                    related_name="commercial_offer",
                    on_delete=django.db.models.deletion.PROTECT,
                )),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="mojpropoffer",
            constraint=models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="mojprop_offer_positive_amount",
            ),
        ),
        migrations.AddConstraint(
            model_name="mojpropoffer",
            constraint=models.CheckConstraint(
                condition=models.Q(delivery_days__gte=1) & models.Q(delivery_days__lte=90),
                name="mojprop_offer_delivery_days_range",
            ),
        ),
    ]
