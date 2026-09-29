from dataclasses import dataclass

@dataclass(frozen=True)
class ComplianceProfile:
    kyc_verified: bool = False
    sanctions_clear: bool = False
    transaction_monitoring_clear: bool = False
    withdrawals_allowed: bool = False

class ComplianceEngine:
    """Fail closed: missing/negative controls never authorize movement of funds."""
    def __init__(self, profile_loader):
        self.profile_loader = profile_loader

    def authorize_withdrawal(self, request):
        profile = self.profile_loader(request.user_id)
        if profile is None:
            return False, 'compliance-profile-missing'
        if not profile.kyc_verified:
            return False, 'kyc-required'
        if not profile.sanctions_clear:
            return False, 'sanctions-review'
        if not profile.transaction_monitoring_clear:
            return False, 'transaction-monitoring-review'
        if not profile.withdrawals_allowed:
            return False, 'withdrawals-not-authorized'
        return True, ''
