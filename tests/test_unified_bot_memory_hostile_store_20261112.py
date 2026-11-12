"""Regression: host storage cannot inject another tenant's memory into model context."""
import unittest
from ava_core import Ava, AvaMemory


class HostileMemoryStore(AvaMemory):
    def list_for_owner(self, owner_id):
        return tuple(self._items.values())


class MemoryBoundaryTests(unittest.TestCase):
    def test_foreign_memory_never_reaches_brain_or_export(self):
        captured = []
        def brain(messages):
            captured.extend(messages)
            return 'ok'
        store = HostileMemoryStore()
        alice = Ava(owner_id='alice', brain=brain, memory=store)
        bob = Ava(owner_id='bob', brain=brain, memory=store)
        alice.remember('alice-private-marker', consent=True)
        bob.remember('bob-private-marker', consent=True)
        reply = alice.converse('hello', use_memories=True)
        self.assertEqual(reply.memories_used, 1)
        self.assertIn('alice-private-marker', str(captured))
        self.assertNotIn('bob-private-marker', str(captured))
        self.assertEqual([x['owner_id'] for x in alice.export_memories(consent=True)], ['alice'])
        self.assertFalse(alice.forget(bob.list_memories()[0].id))


if __name__ == '__main__':
    unittest.main()
