"""Remove a false invoice uniqueness rule.

Two different orders may legitimately quote the same native amount to the
same merchant. Replay protection belongs to the persisted transaction receipt
(network, tx_hash), while order identity is already one-to-one.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("mpw_commerce", "0003_buyerwalletchallenge_commerceorderrequest"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="commerceinvoice",
            name="mpw_commerce_unique_native_amount",
        ),
    ]
