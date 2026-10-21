"""Source-only operational heartbeat. Never execute against live cPanel by default."""
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('moj_commerce','0003_scanning_state')]
    operations = [
        migrations.CreateModel(
            name='ScannerRun',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('finished_at', models.DateTimeField(null=True, blank=True)),
                ('status', models.CharField(max_length=8, default='running', choices=[('running','Running'),('ok','Completed'),('failed','Failed')])),
                ('scanned', models.PositiveIntegerField(default=0)),
                ('fulfilled', models.PositiveIntegerField(default=0)),
                ('failures', models.PositiveIntegerField(default=0)),
                ('discrepancies', models.PositiveIntegerField(default=0)),
                ('manual_review', models.PositiveIntegerField(default=0)),
                ('error_code', models.CharField(max_length=24,blank=True,default='')),
            ],
            options={'indexes':[models.Index(fields=['status','started_at'],name='moj_scan_health_idx')]},
        ),
    ]