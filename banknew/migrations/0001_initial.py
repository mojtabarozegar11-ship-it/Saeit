from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="LoginChallenge", fields=[
            ("nonce_digest", models.CharField(max_length=64, primary_key=True, serialize=False)),
            ("session_digest", models.CharField(max_length=64, db_index=True)),
            ("issued_at", models.DateTimeField(db_index=True)),
            ("consumed_at", models.DateTimeField(null=True, blank=True)),
        ], options={"db_table":"mojpay_google_login_challenges"}),
        migrations.CreateModel(name="GoogleAccountLink", fields=[
            ("id", models.BigAutoField(primary_key=True, serialize=False)),
            ("google_subject", models.CharField(max_length=255, unique=True)),
            ("verified_email", models.EmailField(max_length=320)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("user", models.OneToOneField(to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="mojpay_google_identity")),
        ], options={"db_table":"mojpay_google_account_links"}),
    ]
