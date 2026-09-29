from .domain import UnitRuntime, UnitState, UnitKind

class Registry:
    def __init__(self): self.units={}
    def register(self, spec):
        if spec.id in self.units and self.units[spec.id].spec.version >= spec.version: raise ValueError('version must increase')
        runtime=UnitRuntime(spec); self.units[spec.id]=runtime; return runtime
    def active(self): return tuple(u for u in self.units.values() if u.state is UnitState.ACTIVE)

class EconomicFactory:
    def __init__(self, registry=None): self.registry=registry or Registry()
    def create_team(self, opportunity_id, mission, agent_spec, robot_specs):
        if agent_spec.kind is not UnitKind.AGENT: raise ValueError('agent required')
        if not robot_specs or any(r.kind is not UnitKind.ROBOT for r in robot_specs): raise ValueError('execution robot required')
        return {'opportunity':opportunity_id,'mission':mission,'agent':self.registry.register(agent_spec),'robots':[self.registry.register(r) for r in robot_specs]}
    def activate_demo_validated(self, runtime, demo_passed):
        if not demo_passed: raise ValueError('demo validation required')
        runtime.state=UnitState.ACTIVE; return runtime
