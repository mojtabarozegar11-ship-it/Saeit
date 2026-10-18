"""Loads the user's Gen64 controller from a quarantined local vendor subtree.

Never imports the legacy Celery/Django self-modifying packages. Import only upon
an explicit command. Runtime callbacks are supplied by this site, not the ZIP.
"""
from pathlib import Path
import sys

def new_controller():
    vendor = str(Path(__file__).resolve().parent / 'vendor')
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    from master_gen64 import Generation64Controller
    return Generation64Controller()

def route_once(job_id, callback):
    if not isinstance(job_id, str) or not 1 <= len(job_id) <= 100:
        raise ValueError('invalid_request_id')
    outcome = new_controller().run({'approved_research': callback}, request_id=job_id,
                                   min_candidates=1, max_candidates=1, cache_safe=False)
    if not outcome.ok:
        raise RuntimeError('gen64_job_failed')
    return outcome.value
