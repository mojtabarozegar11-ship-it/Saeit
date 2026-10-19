"""Pure, versioned claim guards for race-safe local agent completion.

The database update must match this original claim. This helper never
runs a worker or changes records on its own; it is testable without Django.
"""
from datetime import datetime


def completion_guard(*, task_id, started_at, attempts):
    if type(task_id) is not int or task_id < 1:
        raise ValueError('invalid_task_id')
    if not isinstance(started_at, datetime) or started_at.tzinfo is None:
        raise ValueError('invalid_started_at')
    if type(attempts) is not int or not 1 <= attempts <= 32767:
        raise ValueError('invalid_attempts')
    return {
        'pk': task_id,
        'state': 'running',
        'started_at': started_at,
        'attempts': attempts,
    }
