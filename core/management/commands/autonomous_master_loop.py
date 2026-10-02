from django.core.management.base import BaseCommand
from django.core.management import call_command
from core.autonomous_brain import AutonomousBrain
from core.models import AgentTask
from core.economic_tool_pack import build_economic_gateway
from core.worker_runner import WorkerRunner

class Command(BaseCommand):
    help = "Autonomous observe-decide-execute-verify-replan loop."

    def add_arguments(self, parser):
        parser.add_argument("--max-steps", type=int, default=20)

    def handle(self,*args,**opts):
        brain=AutonomousBrain()
        for step in range(max(1,opts["max_steps"])):
            active=AgentTask.objects.filter(agent__code="economic-master-agent",status="queued").order_by("created_at").first()
            if not active:
                call_command("online_income_cycle")
                active=AgentTask.objects.filter(agent__code="economic-master-agent",status="queued").order_by("created_at").first()
            if not active:
                self.stdout.write("AUTONOMOUS_IDLE"); return
            try:
                done=WorkerRunner(build_economic_gateway()).run(active.pk)
                self.stdout.write(self.style.SUCCESS(
                    f"AUTO step={step+1} task={done.pk} action={done.action_type} verified={done.output_data.get('verified_effect')}"
                ))
            except Exception as exc:
                prereq=brain.prerequisite_from_error(exc)
                self.stdout.write(f"AUTO_REPLAN failed_task={active.pk} reason={exc} prerequisite={prereq or 'unknown'}")
                if not prereq:
                    return
                # Failed task is already safely requeued by WorkerRunner when retries remain.
                # Cancel it as superseded so the inferred prerequisite can run first.
                active.refresh_from_db()
                if active.status=="queued":
                    active.status="cancelled"
                    active.output_data={**(active.output_data or {}),"replanned_to":prereq,"blocker":str(exc)[:1000]}
                    active.save(update_fields=["status","output_data","updated_at"])
                agent=active.agent
                cap=agent.capabilities.filter(code=prereq,active=True).first()
                if not cap:
                    self.stdout.write(f"AUTO_BLOCKED missing_capability={prereq}"); return
                AgentTask.objects.create(agent=agent,action_type=prereq,capability_code=prereq,
                    risk_snapshot=cap.risk_level,input_data={"objective":agent.mission,"replanned_from":active.pk,
                    "reason":str(exc)[:1000]},status="queued")
                continue

            # Stop when progress reaches an external-world boundary rather than
            # pretending an internal artifact equals a sale.
            done.refresh_from_db()
            if done.action_type=="income_growth_experiment":
                self.stdout.write("AUTO_EXTERNAL_BOUNDARY growth experiment prepared; real acquisition requires an authorized external channel.")
                return
