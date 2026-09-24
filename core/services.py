SENSITIVE={"publish","payment","delete_data","deploy","production_change","legal_action","external_write"}
def requires_owner_approval(action,risk="low"): return risk in {"high","critical"} or action in SENSITIVE
