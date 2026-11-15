"""Merge the two previously published core migration heads.

0040 creates the commerce funnel event table; 0041 creates MojPropRequest
from 0039. Both may already have been applied on different environments.
Never rewrite those historical dependencies or run destructive schema changes.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0040_commercefunnelevent"),
        ("core", "0041_mojprop_request"),
    ]

    operations = []
