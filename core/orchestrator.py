from core.models import Agent,AgentTask,ApprovalRequest
from core.services import requires_owner_approval
class MasterAgent:
 def plan(self,project,action,payload,risk="low"):
  agent=Agent.objects.filter(active=True).first()
  if not agent: raise RuntimeError("No active agent")
  task=AgentTask.objects.create(agent=agent,project=project,input_data=payload)
  if requires_owner_approval(action,risk):
   ApprovalRequest.objects.create(action_type=action,target_type="AgentTask",target_id=str(task.pk),reason="Owner approval required",risk=risk,requested_by=project.owner)
   task.status="blocked"; task.save(update_fields=["status","updated_at"])
  return task
