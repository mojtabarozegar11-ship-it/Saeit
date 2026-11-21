from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("command_center", "0007_command_request_queue"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicProcurementNumber",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notice_key", models.CharField(max_length=40, unique=True)),
                ("serial_number", models.PositiveBigIntegerField(db_index=True, unique=True)),
                ("baseline_evidence", models.TextField()),
                ("reserved_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ("serial_number",)},
        ),
    ]
