# Wallet-ownership verification state; source-only migration (NOT applied to live DB).
import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('moj_commerce', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='merchantaddress', name='verified_via',
            field=models.CharField(choices=[
                ('unverified','Not verified'), ('tron-sign-v2','TRON signMessageV2'),
                ('manual','Manual verification (restricted)')],
                default='unverified', max_length=20),
        ),
        migrations.CreateModel(
            name='WalletOwnershipChallenge',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('message', models.CharField(max_length=550)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('expires_at', models.DateTimeField()),
                ('consumed_at', models.DateTimeField(blank=True, null=True)),
                ('address', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                    related_name='ownership_challenge', to='moj_commerce.merchantaddress')),
            ],
        ),
    ]