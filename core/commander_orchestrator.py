"""Commander Gen-15 goal-to-execution orchestration.

This layer bridges intelligence to the controlled execution engine. It only routes
into capabilities already registered in the database/execution adapter registry;
it does not grant permissions or invent unrestricted tools.
"""
from .master_execution import MasterExecutionEngine


class CommanderOrchestrator:
    def __init__(self, engine=None):
        self.engine = engine or MasterExecutionEngine()

    def available_capabilities(self):
        return sorted(self.engine.handlers.keys())

    def execute_capability(self, *, capability_code, input_data, project=None,
                           action_type="execute", owner=None):
        task = self.engine.create_task(
            capability_code=capability_code,
            input_data=input_data,
            project=project,
            action_type=action_type,
        )
        return self.engine.execute(task, owner=owner)

    def run_pending(self, *, limit=20, owner=None):
        return self.engine.run_queued(limit=limit, owner=owner)
