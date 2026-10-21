"""Operator-only command. Cron / cPanel scheduling NOT installed."""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from moj_commerce.scan_purchases import scan_purchases_once, ScanUnavailable


class Command(BaseCommand):
    help='Read-only TRX discovery + safe buyer delivery; no wallet keys or withdrawals'

    def handle(self,*args,**options):
        if connection.vendor!='postgresql':
            raise CommandError('Financial scanning requires PostgreSQL')
        try:
            result=scan_purchases_once()
        except ScanUnavailable as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write('MOJ_COMMERCE_SCAN_COUNTS '+ ' '.join(
            f'{k}={v}' for k,v in sorted(result.items())))