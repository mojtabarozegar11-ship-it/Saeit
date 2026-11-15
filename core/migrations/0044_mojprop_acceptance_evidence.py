"""Record independently reviewable acceptance evidence; never create a payment."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0043_mojprop_digital_inquiry")]
    operations = [
        migrations.AddField(
            model_name="mojpropoffer", name="accepted_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="mojpropoffer", name="acceptance_reference",
            field=models.CharField(max_length=180, blank=True, default=""),
        ),
    ]
