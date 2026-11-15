"""Merge the public applicant branch with the existing equity-source branch.

This migration only reconciles migration history. It does not change data,
enable funding, enable payouts, or enable live trading.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0002_prop_applicant"),
        ("prop_firm", "0007_equity_broker_source"),
    ]

    operations = []
