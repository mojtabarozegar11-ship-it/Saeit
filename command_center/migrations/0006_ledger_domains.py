from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("command_center", "0005_ledger_audit_event")]
    operations = [
        migrations.AddField(model_name="cyclereport", name="domain", field=models.CharField(choices=[("command", "فرمان و چرخه‌ها"), ("virtual", "سایت‌ها و کسب‌وکار مجازی"), ("physical", "شرکت و کسب‌وکار فیزیکی")], db_index=True, default="command", max_length=12)),
        migrations.AddField(model_name="cycleissue", name="domain", field=models.CharField(choices=[("command", "فرمان و چرخه‌ها"), ("virtual", "سایت‌ها و کسب‌وکار مجازی"), ("physical", "شرکت و کسب‌وکار فیزیکی")], db_index=True, default="command", max_length=12)),
    ]
