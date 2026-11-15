from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("mpw_commerce", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GuestTrxDelivery",
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
                (
                    "email",
                    models.EmailField(max_length=254),
                ),
                (
                    "invoice_state",
                    models.CharField(default="pending", max_length=16),
                ),
                (
                    "invoice_attempts",
                    models.PositiveSmallIntegerField(default=0),
                ),
                (
                    "receipt_state",
                    models.CharField(default="pending", max_length=16),
                ),
                (
                    "receipt_attempts",
                    models.PositiveSmallIntegerField(default=0),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="mpw_guest_trx_delivery",
                        to="core.order",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["invoice_state", "invoice_attempts"],
                        name="mpw_guest_inv_outbox_idx",
                    ),
                    models.Index(
                        fields=["receipt_state", "receipt_attempts"],
                        name="mpw_guest_rcpt_outbox_idx",
                    ),
                ],
            },
        ),
    ]
