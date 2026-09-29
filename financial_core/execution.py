from dataclasses import dataclass
from .domain import Environment

@dataclass(frozen=True)
class ExecutionResult:
    request_id: str; status: str; external_id: str|None=None; detail: str=''

class Connector:
    def execute(self, request): raise NotImplementedError

class DemoConnector(Connector):
    def __init__(self): self.executed={}
    def execute(self, request):
        if request.environment is not Environment.DEMO: raise PermissionError('demo connector refuses real execution')
        if request.id in self.executed: return self.executed[request.id]
        result=ExecutionResult(request.id,'accepted',f'demo:{request.id}')
        self.executed[request.id]=result; return result

class ExecutionEngine:
    def __init__(self, risk_gate, connector): self.risk=risk_gate; self.connector=connector
    def execute(self, request, owner_approved=False):
        ok, reason=self.risk.authorize(request, owner_approved)
        if not ok: return ExecutionResult(request.id,'blocked',detail=reason)
        return self.connector.execute(request)
