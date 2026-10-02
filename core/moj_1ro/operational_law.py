"""Owner's standing mission, read by the live planner rather than a display-only prompt."""
import hashlib, json
from pathlib import Path
LAW_PATH = Path(__file__).with_name('operational_constitution.json')

def current():
    raw = LAW_PATH.read_bytes()
    document = json.loads(raw)
    if document.get('version') != 2 or document.get('identity') != 'moj_1ro_1':
        raise ValueError('unsupported_operational_constitution')
    return {**document, 'sha256': hashlib.sha256(raw).hexdigest()}

def automatic_allowed(domain, operation, payload):
    law = current()
    return operation == 'audit' or (
        domain == 'self_improvement' and operation == 'repair' and
        set(payload) == {'recipe'} and payload['recipe'] in law['automatic_repairs'])

def priority(domain):
    return current()['priorities'][domain]
