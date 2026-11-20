"""Compatibility quarantine for retired pre-isolation MOJ PROP modules.

The public English Starter30 flow uses only the PropSimulation* models. These
names remain importable for dormant historical modules so an accidental import
fails closed with an explicit error instead of silently reaching legacy tables.
"""


class LegacyPropFirmDisabled(RuntimeError):
    """Raised when retired legacy MOJ PROP persistence is invoked."""


class _DisabledEnum:
    def __getattr__(self, name):
        raise LegacyPropFirmDisabled(
            "retired legacy MOJ PROP model metadata is disabled"
        )


class _DisabledManager:
    def __getattr__(self, name):
        def disabled(*args, **kwargs):
            raise LegacyPropFirmDisabled(
                "retired legacy MOJ PROP persistence is disabled; "
                "use the isolated PropSimulation* flow"
            )

        return disabled


class _DisabledLegacyModel:
    objects = _DisabledManager()
    Kind = _DisabledEnum()
    Status = _DisabledEnum()
    Review = _DisabledEnum()


def _retired_model(name):
    return type(name, (_DisabledLegacyModel,), {"__module__": __name__})


PropAccount = _retired_model("PropAccount")
PropChallengeEnrollment = _retired_model("PropChallengeEnrollment")
PropDecisionLog = _retired_model("PropDecisionLog")
PropEquityObservation = _retired_model("PropEquityObservation")
PropExecution = _retired_model("PropExecution")
PropInterest = _retired_model("PropInterest")
PropPlan1Invoice = _retired_model("PropPlan1Invoice")
PropPlan1Receipt = _retired_model("PropPlan1Receipt")
PropProfitAllocation = _retired_model("PropProfitAllocation")
PropProfitJournalLine = _retired_model("PropProfitJournalLine")
PropRewardCommitment = _retired_model("PropRewardCommitment")
PropRewardReserveAllocation = _retired_model("PropRewardReserveAllocation")
PropSocialEvidence = _retired_model("PropSocialEvidence")
PropTrader = _retired_model("PropTrader")
TronSettlementLedger = _retired_model("TronSettlementLedger")
