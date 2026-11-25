from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("mpw_commerce", "0002_buyerwalletchallenge_commerceorderrequest"),
    ]
    operations = [
        migrations.CreateModel(
            name="SignalSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("plan_id", models.CharField(max_length=40)),
                ("price_usd", models.DecimalField(max_digits=14, decimal_places=2)),
                ("term_weeks", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("item", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="mpw_signal_subscription", to="core.orderitem")),
            ],
            options={"constraints": [
                models.CheckConstraint(
                    condition=(models.Q(plan_id="education-monthly", term_weeks=4, price_usd="29.90")
                               | models.Q(plan_id="education-quarterly", term_weeks=12, price_usd="79.90")),
                    name="mpw_signal_fixed_terms_v1"),
            ]},
        ),
    ]
