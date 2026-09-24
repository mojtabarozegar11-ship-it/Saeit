from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

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
            ],
        ),
        migrations.CreateModel(
            name="ChatSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(blank=True, max_length=300)),
                ("status", models.CharField(default="active", max_length=20)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="master_agent_chat_sessions", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ChatMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("role", models.CharField(max_length=20)),
                ("content", models.TextField()),
                ("metadata", models.JSONField(default=dict)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="core.chatsession")),
            ],
        ),
        migrations.AddField(
            model_name="agentcapability",
            name="agents",
            field=models.ManyToManyField(blank=True, related_name="capabilities", to="core.agent"),
        ),
        migrations.AddField(
            model_name="agenttask",
            name="action_type",
            field=models.CharField(default="", max_length=100),
        ),
        migrations.AddField(
            model_name="agenttask",
            name="capability_code",
            field=models.CharField(default="", max_length=100),
        ),
        migrations.AddField(
            model_name="agenttask",
            name="risk_snapshot",
            field=models.CharField(default="low", max_length=10),
        ),
        migrations.AddField(
            model_name="agenttask",
            name="execution_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="agenttask",
            name="attempt_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="agenttask",
            name="max_attempts",
            field=models.PositiveIntegerField(default=3),
        ),
        migrations.AddField(
            model_name="approvalrequest",
            name="decision_note",
            field=models.TextField(blank=True),
        ),
    ]
