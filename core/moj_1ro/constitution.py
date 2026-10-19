from dataclasses import dataclass

@dataclass(frozen=True)
class Constitution:
    family: str = 'Moj_1ro'
    version: int = 2
    owner_supremacy: bool = True
    audit_required: bool = True
    evidence_required_for_success: bool = True
    production_self_mutation: bool = True
    protected_actions: tuple[str, ...] = ('payment','credential_write','legal_commitment','fund_transfer','wallet_withdrawal','real_account_trade','private_key','seed_phrase','root_shell','mass_delete','unbounded_spend','kyc','identity_verification','contract_acceptance','terms_acceptance')

    def needs_owner_approval(self, action: str) -> bool:
        return action in self.protected_actions

    def operational_mission(self):
        from .operational_law import current
        return current()
