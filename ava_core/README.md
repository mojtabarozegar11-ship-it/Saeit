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

This component can later become AVA's personal interface to the unified
`Mojtaba.bot.ai` system without creating a duplicate task executor.
