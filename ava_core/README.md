# mojtaba.bot.ai — one unified bot

`MojtabaBot` is the **only canonical runtime**. Conversation (affectionately
called "آوا" by the owner), goals, memory, code evolution, products, trading,
games, messaging and future services must all use this one runtime and its
`CapabilityHub`, not run as independently branded robots. `AvaRuntime` and
`Ava` remain import aliases for old code, not additional bot processes.

This repository currently contains a **foundation**, not a deployed commercial
agent. No trading, live messaging, purchasing, hosting administration, paid
model, or external service adapter is connected by default.

## Included

- One verified software identity: `mojtaba.bot.ai`, with "آوا" as a nickname.
- A single capability bus for future host-connected work modules, with typed
  actions, independent authorization for external effects, anti-replay within
  the running process, and adapter-reported receipts.
- An injectable `Brain` interface, avoiding mandatory paid providers.
- Owner-scoped, opt-in memory: explicit permission to store, separate permission
  to include saved context in a model request, and owner-controlled deletion.
- Ephemeral storage by default: no secrets or personal history on disk.
- Standard-library regression checks, with no third-party dependency.
- A goal-selection director: an injected proposer can invent goals in any
  domain. Choosing an objective does not execute it or grant external access.
- A manufacturer-independent, read-only body interface and a simulation-only
  command gateway that enforces independent authorization, state checks,
  bounded movement, emergency stop, and replay prevention.

## Unified public entrypoint

```python
from ava_core import (
    ActionRequest, AdapterResult, CapabilitySpec, MojtabaBot, OperationSpec,
)

# This is a host-owned local calculation, NOT a live broker or service.
bot = MojtabaBot(
    owner_id="authenticated-owner-id",
    brain=verified_brain,
    propose_goals=verified_goal_proposer,
    capabilities=((
        CapabilitySpec("economics", (OperationSpec("calculate", "local"),)),
        lambda request: AdapterResult(True, "Calculated using the supplied inputs"),
    ),),
)
assert bot.bot_name == "mojtaba.bot.ai"
receipt = bot.execute_action(ActionRequest(
    "unique-request-id", "authenticated-owner-id", "economics", "calculate", {},
))
assert receipt.result.success and not receipt.independently_verified
```

`verified_brain` and `verified_goal_proposer` are host-supplied integration
points, not functions bundled with this package. A module is connected only
when the authenticated host registers its adapter; registration is not proof
that an external service is available. Every nonlocal operation, including
reads of external systems, requires an independent authorization callback.
The in-memory anti-replay state is not sufficient for reliable production
payments or trades; these require a durable transactional idempotency store.

## Future physical embodiment: safe software boundary

```python
from ava_core import BodyCommand, EmbodimentGateway, SimulatedBody

body = SimulatedBody(robot_id="ava-sim")
gateway = EmbodimentGateway(
    owner_id="authenticated-owner-id",
    body=body,
    # Illustrative authorization for a single local simulation only.
    authorize=lambda owner, cmd: owner == "authenticated-owner-id" and cmd.request_id == "demo-1",
)
receipt = gateway.simulate(BodyCommand(
    request_id="demo-1", robot_id="ava-sim", kind="say", text="درود فراوان"
))
assert receipt.simulated and body.last_speech == "درود فراوان"
```

`RobotAdapter.observe()` gives a future hardware driver read-only status
access. This package **refuses to actuate any hardware**, including subclasses
of its simulator. Real-world motion needs separate hardware safety controls,
physical emergency stop, authenticated permissions, and verified vendor drivers.
No camera, microphone, live model, or purchased device is connected here.

## Independent goal selection (not action execution)

```python
from ava_core import AutonomousGoalDirector, GoalProposal

def propose_goals(history):
    # Replace with a configured reasoning model when authorized.
    return [GoalProposal(
        goal_id="improve-scientific-writing",
        description="Design a better citation-checking workflow",
        expected_value=5, feasibility=4, learning_value=5,
    )]

director = AutonomousGoalDirector(owner_id="authenticated-owner-id", proposer=propose_goals)
decision = director.decide()
assert decision.selected and decision.selected.goal_id == "improve-scientific-writing"
```

The proposer is illustrative, **not a connected AI model**. This component
chooses intentions but does not execute them. An independent host permission
gate must verify every eventual action; a goal proposal's self-declared flags
are untrusted. It does not infer consciousness or independent subjective wishes.
It neither removes human accountability nor grants itself access or money.

## Conversation is one module, not a second bot

```python
from ava_core import MojtabaBot

def configured_brain(messages):
    # Connect a verified existing local model or approved provider here.
    # This function must return the model's text response.
    raise NotImplementedError("Configure a brain before use")

bot = MojtabaBot(
    owner_id="authenticated-owner-id", brain=configured_brain,
    propose_goals=verified_goal_proposer,
)
bot.remember("Owner-approved preference", consent=True)
response = bot.converse("سلام آوا", use_memories=True)
```

**Integration requirements:** Authenticate the owner before constructing an
instance; authorize model-provider data sharing; protect persisted memories
using encrypted storage and backups; use the single `CapabilityHub` for
host-configured operations and separate verified adapters for voice, services
and robotics. Never interpret a selected goal as authorization to spend,
trade, send messages or deploy.

## Verification

`python -m unittest discover -s tests -p 'test_ava_core.py' -v`

`python -m unittest discover -s tests -p 'test_ava_goals.py' -v`

`python -m unittest discover -s tests -p 'test_ava_embodiment.py' -v`

`python -m unittest discover -s tests -p 'test_mojtaba_bot.py' -v`

Existing modules are internal parts of mojtaba.bot.ai. Legacy files are kept
for compatibility until all consuming code and real integrations are mapped;
deletion or deployment requires a verified migration and owner approval.
