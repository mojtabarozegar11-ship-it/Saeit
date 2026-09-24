from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0003_approval_decision_note")]
    operations = [
        migrations.CreateModel(
            name="AgentCapability",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.SlugField(unique=True)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("risk_level", models.CharField(default="low", max_length=10)),
                ("active", models.BooleanField(default=True)),
                ("agents", models.ManyToManyField(blank=True, related_name="capabilities", to="core.agent")),
            ],
        ),
    ]
