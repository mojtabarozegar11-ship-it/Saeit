"""Reserve 72 public advertisement numbers strictly AFTER a verified existing high-watermark.

Usage (read-only planning):
  python manage.py register_direct_procurement_notices --last-existing-number N --evidence "Reference to verified old ledger"
Actual reservation (only after verification):
  python manage.py register_direct_procurement_notices --last-existing-number N --evidence "Reference to verified old ledger" --apply

Never assume that provisional source ids ZM-SUP-001 and ZM-EQP-001 are public
advertisement numbers; they are merely stable keys into this reservation ledger.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from command_center.models import PublicProcurementNumber
from core.procurement_notices import get_public_procurement_notices


def ordered_notice_keys():
    grouped, _ = get_public_procurement_notices()
    return [notice["id"] for kind in ("supply", "equipment") for notice in grouped[kind]]


class Command(BaseCommand):
    help = "Reserve the next 72 advertisement numbers after a verified existing last number (dry run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--last-existing-number", required=True, type=int,
                            help="Highest PUBLIC ad number verified across ALL existing registration sources")
        parser.add_argument("--evidence", required=True,
                            help="Short description of the authoritative source proving the last registered number")
        parser.add_argument("--apply", action="store_true",
                            help="Reserve numbers permanently; otherwise show preview only")

    def handle(self, *args, **options):
        highwater = options["last_existing_number"]
        evidence = options["evidence"].strip()
        if highwater < 0:
            raise CommandError("Last existing advertisement number must be >= 0.")
        if len(evidence) < 12:
            raise CommandError("Provide verifiable evidence for the last registered public advertisement number.")
        keys = ordered_notice_keys()
        if len(keys) != 72 or len(set(keys)) != 72:
            raise CommandError("72 unique source advertisement keys are required.")
        try:
            with transaction.atomic():
                registrations = list(PublicProcurementNumber.objects.select_for_update().order_by("serial_number"))
                existing_by_key = {item.notice_key: item for item in registrations}
                existing_keys = set(existing_by_key)
                target_keys = set(keys)
                if target_keys & existing_keys:
                    if target_keys <= existing_keys:
                        numbers = [existing_by_key[key].serial_number for key in keys]
                        if min(numbers) <= highwater:
                            raise CommandError("The claimed historic high-watermark conflicts with already reserved new advertisements.")
                        self.stdout.write(
                            f"Already reserved: {len(keys)} ads, numbers {min(numbers)} through {max(numbers)}. No changes."
                        )
                        return
                    raise CommandError("Partial previous reservation detected. Refusing to renumber or create duplicates.")
                registered_max = max((item.serial_number for item in registrations), default=0)
                # Django row primary keys are NOT published auction serial numbers.
                start = max(highwater, registered_max) + 1
                end = start + len(keys) - 1
                self.stdout.write(
                    f"Verified public-ad high-watermark: {highwater}; "
                    f"reserved public-ad max: {registered_max}; proposed official range: {start}..{end}."
                )
                if not options["apply"]:
                    self.stdout.write("DRY RUN ONLY. No numbers have been reserved.")
                    return
                # Do not silently reserve a different range than the verified
                # GitHub source-of-truth mapping. Reconcile the live register
                # and revise the proposal if a higher number has appeared.
                grouped, _ = get_public_procurement_notices()
                expected = [item["proposed_public_number"]
                            for kind in ("supply", "equipment") for item in grouped[kind]]
                actual = list(range(start, end + 1))
                if actual != expected:
                    raise CommandError(
                        f"Number range changed: proposed {expected[0]}..{expected[-1]}, "
                        f"but live registry indicates {start}..{end}. Update the "
                        "verified baseline and draft mappings before reservation."
                    )
                if not evidence:
                    raise CommandError("Source evidence is required for actual reservation.")
                PublicProcurementNumber.objects.bulk_create([
                    PublicProcurementNumber(
                        notice_key=key,
                        serial_number=start + index,
                        baseline_evidence=evidence,
                    ) for index, key in enumerate(keys)
                ])
                self.stdout.write(self.style.SUCCESS(
                    f"Successfully reserved 72 unique permanent public notice numbers: {start}..{end}."
                ))
        except IntegrityError as exc:
            raise CommandError("Number collision: transaction rolled back; re-read the register and retry.") from exc
