from django.db import migrations
from config.mojprop_db_router import MOJPROP_DB_ALIAS


def create_payment_table(apps, schema_editor):
    if schema_editor.connection.alias != MOJPROP_DB_ALIAS:
        return
    model = apps.get_model("prop_firm", "PropSimulationPayment")
    table_names = set(schema_editor.connection.introspection.table_names())
    if model._meta.db_table not in table_names:
        schema_editor.create_model(model)


def drop_payment_table(apps, schema_editor):
    if schema_editor.connection.alias != MOJPROP_DB_ALIAS:
        return
    model = apps.get_model("prop_firm", "PropSimulationPayment")
    table_names = set(schema_editor.connection.introspection.table_names())
    if model._meta.db_table in table_names:
        schema_editor.delete_model(model)


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0002_starter30_payment"),
    ]

    operations = [
        migrations.RunPython(
            create_payment_table, drop_payment_table,
            hints={"model_name": "propsimulationpayment"},
        ),
    ]
