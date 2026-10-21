"""Machine-readable alert probe for owner-approved external schedulers.

No outbound message is sent and no scanner/order state is changed. Exit-code
monitoring requires an operator-selected schedule and separate alert channel.
"""
import json

from django.core.management.base import BaseCommand, CommandError
from moj_commerce.operations import scanner_health
from moj_commerce.operational_alerts import assess_scanner_alerts


class Command(BaseCommand):
    help = 'Read-only sanitized scanner alert signal; optional nonzero exit for monitors.'

    def add_arguments(self, parser):
        parser.add_argument('--strict', action='store_true',
                            help='Exit unsuccessfully for warning/critical attention.')

    def handle(self, *args, **options):
        report = assess_scanner_alerts(scanner_health())
        self.stdout.write('MOJ_COMMERCE_HEALTH ' +
                          json.dumps(report, ensure_ascii=True, sort_keys=True))
        if options['strict'] and report['operator_action_required']:
            # Fixed error code: no buyer IDs, RPC messages, wallet secrets.
            raise CommandError('MOJ_COMMERCE_MONITOR_ATTENTION')
