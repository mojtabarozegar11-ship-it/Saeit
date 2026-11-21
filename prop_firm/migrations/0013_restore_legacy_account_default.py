from decimal import Decimal
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0012_simulation_account")]
    operations = [migrations.AlterField(
        model_name="propaccount", name="starting_capital_usd",
        field=models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("100.00")),
    )]
