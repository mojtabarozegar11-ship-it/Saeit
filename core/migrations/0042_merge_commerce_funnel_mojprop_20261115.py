"""Join two already independent Django core migration lines (no schema rewrite).

Both parents branch only from core.0039 and create separate models:
CommerceFunnelEvent and MojPropRequest. Running their operations in either
valid order is supported; this merge only removes the multiple-leaf CI block.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0040_commercefunnelevent"),
        ("core", "0041_mojprop_request"),
    ]

    operations = []
