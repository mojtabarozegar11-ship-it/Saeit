from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0016_simulation_event")]
    operations = [
        migrations.AddField(model_name="propsimulationaccount", name="event_head_sequence",
                            field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="propsimulationaccount", name="event_head_digest",
                            field=models.CharField(max_length=64, default="0" * 64)),
    ]
