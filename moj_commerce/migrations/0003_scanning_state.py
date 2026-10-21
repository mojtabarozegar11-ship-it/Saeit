# Source-only migration. NOT executed on real cPanel databases.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[('moj_commerce','0002_wallet_proof')]
    operations=[
        migrations.CreateModel(
            name='PurchaseScanState',
            fields=[
                ('id',models.BigAutoField(primary_key=True,serialize=False)),
                ('next_scan_ms',models.BigIntegerField(db_index=True,default=0)),
                ('last_scan_ms',models.BigIntegerField(default=0)),
                ('failures',models.PositiveSmallIntegerField(default=0)),
                ('purchase',models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                related_name='scan_state',to='moj_commerce.purchase')),
            ],
        ),
        migrations.CreateModel(
            name='PaymentDiscrepancy',
            fields=[
                ('id',models.BigAutoField(primary_key=True,serialize=False)),
                ('txid',models.CharField(max_length=64,unique=True)),
                ('amount_sun',models.BigIntegerField()),
                ('kind',models.CharField(choices=[('underpaid','Underpaid'),('overpaid','Overpaid')],max_length=12)),
                ('observed_at',models.DateTimeField(auto_now_add=True)),
                ('purchase',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             related_name='payment_discrepancies',to='moj_commerce.purchase')),
            ],
        ),
    ]