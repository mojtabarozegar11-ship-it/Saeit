from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("mpw_commerce", "0004_signalresearchissue"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="signalsubscription",
            name="mpw_signal_fixed_terms_v1",
        ),
        migrations.AddConstraint(
            model_name="signalsubscription",
            constraint=models.CheckConstraint(
                condition=(
                    Q(plan_id="education-weekly", term_weeks=1, price_usd="9.90")
                    | Q(plan_id="education-monthly", term_weeks=4, price_usd="29.90")
                    | Q(plan_id="education-quarterly", term_weeks=12, price_usd="79.90")
                ),
                name="mpw_signal_fixed_terms_v1",
            ),
        ),
    ]
