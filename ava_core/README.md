# AVA — private digital companion core

AVA is a provider-neutral Python foundation for a personal conversational
assistant. It is **not** a conscious entity, a physical robot, a trading bot,
or a deployed application. It does not call the internet, buy anything, message
people, or change VPS settings.

## Included

- A consistent Persian-capable identity and truthful behavior contract.
- An injectable `Brain` interface, avoiding mandatory paid providers.
- Owner-scoped, opt-in memory: explicit permission to store, separate permission
  to include saved context in a model request, and owner-controlled deletion.
- Ephemeral storage by default: no secrets or personal history on disk.
- Standard-library regression checks, with no third-party dependency.
- A goal-selection director: an injected proposer can invent goals; AVA ranks
  independently proposed, reversible, zero-spend *internal* objectives, explains
  rejected goals, and stores evidence-backed outcomes in ephemeral history.
- A manufacturer-independent, read-only body interface and a simulation-only
  command gateway that enforces independent authorization, state checks,
  bounded movement, emergency stop, and replay prevention.

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

## Personality and synthetic emotional expression (draft; not yet verified)

`ava_core/affect.py` defines a trait profile (warmth, curiosity, humor, empathy,
initiative), ephemeral mood-like responses to host-classified events, and a
non-explicit romantic text-style option. These are **simulated affective states**,
not genuine emotions, subjective understanding, sentience, or biological lust.
The component stores no message text and invokes no hardware or outside service.

The romantic mode defaults to off. A trusted host callback must verify adult
status and informed, current consent before enabling each session. Revocation
clears its simulated attraction value. An untrusted model assertion is never
proof of age or consent. Physical intimacy is not supported.

This standalone module is **not connected to the conversational brain**. Its
new regression tests have **not run** because the Python environment is
unavailable. Run `python -m unittest discover -s tests -p 'test_ava_affect.py' -v`
before integration, merge, or deployment.

## Host integration

```python
from ava_core import Ava

def configured_brain(messages):
    # Connect a verified existing local model or approved provider here.
    # This function must return the model's text response.
    raise NotImplementedError("Configure a brain before use")

ava = Ava(owner_id="authenticated-owner-id", brain=configured_brain)
ava.remember("Owner-approved preference", consent=True)
response = ava.converse("سلام آوا", use_memories=True)
```

**Integration requirements:** Authenticate the owner before constructing an
instance; authorize model-provider data sharing; protect persisted memories
using encrypted storage and backups; use the existing `AgentRegistry` and
`ToolGateway` for task approvals and audit; use separate verified adapters for
voice and robotics. Do not route orders, trading, purchases, or outbound
messages through this conversational package.

## Verification

`python -m unittest discover -s tests -p 'test_ava_core.py' -v`

`python -m unittest discover -s tests -p 'test_ava_goals.py' -v`

`python -m unittest discover -s tests -p 'test_ava_embodiment.py' -v`

This component can later become AVA's personal interface to the unified
`Mojtaba.bot.ai` system without creating a duplicate task executor.
