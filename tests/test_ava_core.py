"""Standard-library checks for AVA's privacy and integration boundaries."""

import unittest

from ava_core import Ava, AvaMemory, ConsentError
from ava_core.core import MemoryItem


class AvaCoreTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def brain(messages):
            self.calls.append(messages)
            return "درود مجتبی جان"

        self.brain = brain
        self.shared_store = AvaMemory()
        self.ava = Ava(owner_id="owner-1", brain=brain, memory=self.shared_store)

    def test_no_implicit_memory_writes(self):
        self.ava.converse("سلام")
        self.assertEqual(len(self.ava.list_memories()), 0)

    def test_saving_requires_explicit_consent(self):
        with self.assertRaises(ConsentError):
            self.ava.remember("یک خاطره")

    def test_memory_is_not_sent_without_read_consent(self):
        self.ava.remember("خاطره خصوصی", consent=True)
        reply = self.ava.converse("سلام")
        self.assertEqual(reply.memories_used, 0)
        self.assertNotIn("خاطره خصوصی", str(self.calls[-1]))

    def test_approved_memory_is_sent_only_when_requested(self):
        self.ava.remember("به فارسی گفتگو کن", consent=True)
        reply = self.ava.converse("سلام", use_memories=True)
        self.assertEqual(reply.memories_used, 1)
        self.assertIn("به فارسی گفتگو کن", str(self.calls[-1]))

    def test_owner_isolation_and_deletion(self):
        memory = self.ava.remember("خاطره خصوصی", consent=True)
        other = Ava(owner_id="owner-2", brain=self.brain, memory=self.shared_store)
        self.assertEqual(len(other.list_memories()), 0)
        self.assertFalse(other.forget(memory.id))
        self.assertTrue(self.ava.forget(memory.id))
        self.assertEqual(len(self.ava.list_memories()), 0)

    def test_export_requires_consent_and_is_owner_scoped(self):
        saved = self.ava.remember("private export", consent=True)
        other = Ava(owner_id="owner-2", brain=self.brain, memory=self.shared_store)
        with self.assertRaises(ConsentError):
            self.ava.export_memories()
        self.assertEqual(other.export_memories(consent=True), ())
        exported = self.ava.export_memories(consent=True)
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["id"], saved.id)
        self.assertEqual(exported[0]["owner_id"], "owner-1")
        self.assertEqual(exported[0]["text"], "private export")
        self.assertTrue(self.ava.forget(saved.id))
        self.assertEqual(self.ava.export_memories(consent=True), ())

    def test_memory_context_is_bounded_and_owner_scoped(self):
        for i in range(25):
            self.ava.remember(f"memory-{i}", consent=True)
        other = Ava(owner_id="owner-2", brain=self.brain, memory=self.shared_store)
        other.remember("other-owner-secret", consent=True)
        reply = self.ava.converse("سلام", use_memories=True)
        self.assertEqual(reply.memories_used, 20)
        context = str(self.calls[-1])
        self.assertNotIn("memory-0", context)
        self.assertIn("memory-24", context)
        self.assertNotIn("other-owner-secret", context)

    def test_memory_context_total_character_budget(self):
        self.ava.remember("A" * 5000, consent=True)
        self.ava.remember("recent-short", consent=True)
        reply = self.ava.converse("سلام", use_memories=True)
        self.assertEqual(reply.memories_used, 1)
        context = str(self.calls[-1])
        self.assertIn("recent-short", context)
        self.assertNotIn("A" * 5000, context)

    def test_duplicate_memory_id_cannot_overwrite_another_owner(self):
        original = self.ava.remember("owner-one-secret", consent=True)
        other = Ava(owner_id="owner-2", brain=self.brain, memory=self.shared_store)
        with self.assertRaises(ValueError):
            self.shared_store.add(MemoryItem(
                id=original.id, owner_id="owner-2",
                text="replacement", created_at=original.created_at
            ))
        self.assertEqual(self.ava.list_memories(), (original,))
        self.assertEqual(other.list_memories(), ())

    def test_reply_and_validation(self):
        self.assertEqual(self.ava.converse("سلام").text, "درود مجتبی جان")
        with self.assertRaises(ValueError):
            self.ava.converse("  ")
        with self.assertRaises(ValueError):
            Ava(owner_id=" ", brain=self.brain)


if __name__ == "__main__":
    unittest.main()
