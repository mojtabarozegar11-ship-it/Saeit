from django.core.management.base import BaseCommand

from core.models import ApprovalRequest
from core.operation_executor import execute_approved_chat_operation


class Command(BaseCommand):
    help = "Execute approved ordinary-chat operations exactly once."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 50))
        approvals = ApprovalRequest.objects.filter(
            status="approved", target_type="ChatOperation"
        ).order_by("created_at")[:limit]
        executed = 0
        failed = 0
        for approval in approvals:
            try:
                result = execute_approved_chat_operation(approval)
                if result.get("status") == "executed":
                    executed += 1
                self.stdout.write(self.style.SUCCESS(
                    f"CHAT_OPERATION approval={approval.pk} status={result.get('status')}"
                ))
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    f"CHAT_OPERATION approval={approval.pk} failed={type(exc).__name__}"
                )
        self.stdout.write(f"CHAT_OPERATIONS_EXECUTED={executed}")
        self.stdout.write(f"CHAT_OPERATIONS_FAILED={failed}")
