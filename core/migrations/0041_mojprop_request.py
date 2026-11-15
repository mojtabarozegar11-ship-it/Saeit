from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0040_commercefunnelevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="MojPropRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("request_id", models.CharField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("email", models.EmailField(max_length=254)),
                ("route", models.CharField(choices=[("blueprint", "Prop-program design"), ("signals", "Educational signals and market brief"), ("brief", "Private market brief"), ("audit", "mojtaba.bot.ai commercial-gate audit")], max_length=30)),
                ("horizon", models.CharField(choices=[("urgent", "Today / urgent"), ("week", "This week"), ("month", "This month"), ("review", "Initial review only")], max_length=20)),
                ("notes", models.TextField()),
                ("consent", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("new", "New"), ("reviewing", "Reviewing"), ("offer_sent", "Written offer sent"), ("approved", "Approved"), ("delivered", "Delivered"), ("closed", "Closed"), ("spam", "Spam / rejected")], default="new", max_length=20)),
                ("source", models.CharField(default="moj-prop", max_length=80)),
                ("ip_hash", models.CharField(blank=True, default="", max_length=64)),
                ("user_agent", models.CharField(blank=True, default="", max_length=300)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("internal_note", models.TextField(blank=True, default="")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="mojproprequest",
            index=models.Index(fields=["status", "created_at"], name="core_mojprop_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="mojproprequest",
            index=models.Index(fields=["email", "created_at"], name="core_mojprop_email_created_idx"),
        ),
        migrations.AddIndex(
            model_name="mojproprequest",
            index=models.Index(fields=["ip_hash", "created_at"], name="core_mojprop_ip_created_idx"),
        ),
    ]
