"""Merge two *already existing* prop_firm migration histories without schema DDL.

GitHub/source-sync legacy: 0001_initial through 0010_reward_reserve_ledger
Isolated Starter30: 0001_simulation_isolation through 0007_alter_propsimulationaccount_policy_version

IMPORTANT: 15 DeleteModel operations below are STATE-ONLY. They remove obsolete
historical ORM declarations from Django's future migration state, NOT rows,
tables or constraints in either database. Physical historical tables remain
preserved on the original default DB. New live ORM contains only the seven
isolated simulation models.

Do NOT copy source-sync/.../0011_simulation_isolation.py into the active
migrations folder: it recreates five models already present in the new branch.
This bridge is NOT permission to run migrations, enable payments, alter
routers, or modify legacy records. Require verified private isolated DB
restore, both-DB graph checks, DDL review, and supervised cutover.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0010_reward_reserve_ledger"),
        ("prop_firm", "0007_alter_propsimulationaccount_policy_version"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="PropAccount"),
                migrations.DeleteModel(name="PropChallengeEnrollment"),
                migrations.DeleteModel(name="PropDecisionLog"),
                migrations.DeleteModel(name="PropEquityObservation"),
                migrations.DeleteModel(name="PropExecution"),
                migrations.DeleteModel(name="PropInterest"),
                migrations.DeleteModel(name="PropPlan1Invoice"),
                migrations.DeleteModel(name="PropPlan1Receipt"),
                migrations.DeleteModel(name="PropProfitAllocation"),
                migrations.DeleteModel(name="PropProfitJournalLine"),
                migrations.DeleteModel(name="PropRewardCommitment"),
                migrations.DeleteModel(name="PropRewardReserveAllocation"),
                migrations.DeleteModel(name="PropSocialEvidence"),
                migrations.DeleteModel(name="PropTrader"),
                migrations.DeleteModel(name="TronSettlementLedger"),
                ],
            ),
        ]
