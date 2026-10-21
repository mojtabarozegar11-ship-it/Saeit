"""Sanitized fail-closed operations alerts. No money movement or notifications."""
from __future__ import annotations

_ALLOWED = {'disabled', 'not_configured', 'never_run', 'running',
            'stale', 'degraded', 'healthy'}
_LEVEL = {'disabled': 'paused', 'not_configured': 'critical',
          'never_run': 'warning', 'running': 'info',
          'stale': 'critical', 'degraded': 'critical', 'healthy': 'ok'}
_RANK = {'ok': 0, 'info': 1, 'paused': 2, 'warning': 3, 'critical': 4}


def assess_scanner_alerts(snapshot: dict) -> dict:
    """Machine-readable severity + fixed codes, never free-text RPC payloads."""
    status = snapshot.get('status')
    if status not in _ALLOWED:
        raise ValueError('Unknown scanner health state')
    severity = _LEVEL[status]
    codes = [f'scanner_{status}'] if status != 'healthy' else []
    for key, code, minimum in (
        ('overdue_scans', 'scan_backlog', 'warning'),
        ('missing_scan_states', 'missing_scan_schedule', 'critical'),
        ('orders_with_repeated_scan_failures', 'scan_retry_exhaustion', 'critical'),
        ('payment_discrepancies', 'payment_requires_manual_review', 'warning'),
    ):
        count = snapshot.get(key, 0)
        if type(count) is not int or count < 0:
            raise ValueError('Invalid alert aggregate')
        if count:
            codes.append(code)
            if _RANK[minimum] > _RANK[severity]:
                severity = minimum
    # Pause is intentional when disabled; a production deployment is NOT healthy.
    return {'scanner_status': status, 'severity': severity,
            'codes': codes,
            'financial_processing_confirmed': False,
            'operator_action_required': severity in ('warning', 'critical'),
            'automatic_payment_recovery_permitted': False}
