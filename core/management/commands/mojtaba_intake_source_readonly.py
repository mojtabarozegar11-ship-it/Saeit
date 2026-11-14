"""Operator-only CLI: zero-I/O source-of-truth configuration diagnostic.

python manage.py mojtaba_intake_source_readonly
No customer record, raw environment secret, hostname/IP or payments exposed.
"""
import json
from django.core.management.base import BaseCommand

from core.service_intake_routing import service_intake_source_snapshot


class Command(BaseCommand):
    help = "Report company intake routing decisions without private user records."

    def handle(self, *args, **options):
        result = service_intake_source_snapshot()
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
