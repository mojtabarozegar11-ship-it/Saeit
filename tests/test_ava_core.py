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

    def test_forget_all_requires_consent_and_preserves_other_owner(self):
        self.ava.remember("one", consent=True)
        self.ava.remember("two", consent=True)
        other = Ava(owner_id="owner-2", brain=self.brain, memory=self.shared_store)
        other.remember("other", consent=True)
        with self.assertRaises(ConsentError):
            self.ava.forget_all()
        self.assertEqual(len(self.ava.list_memories()), 2)
        self.assertEqual(self.ava.forget_all(consent=True), 2)
        self.assertEqual(self.ava.forget_all(consent=True), 0)
        self.assertEqual(len(other.list_memories()), 1)

    def test_forget_all_fails_closed_when_store_refuses_delete(self):
        class RefusingStore(AvaMemory):
            def delete(self, owner_id, memory_id):
                return False

        store = RefusingStore()
        ava = Ava(owner_id="owner-1", brain=self.brain, memory=store)
        ava.remember("must remain", consent=True)
        with self.assertRaises(RuntimeError):
            ava.forget_all(consent=True)
        self.assertEqual(len(ava.list_memories()), 1)

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

    def test_memory_store_rejects_invalid_records(self):
        original = self.ava.remember("valid", consent=True)
        for invalid in (
            MemoryItem("", "owner-1", "text", original.created_at),
            MemoryItem("bad-owner", " ", "text", original.created_at),
            MemoryItem("bad-text", "owner-1", " ", original.created_at),
        ):
            with self.subTest(memory_id=invalid.id):
                with self.assertRaises(ValueError):
                    self.shared_store.add(invalid)
        self.assertEqual(self.ava.list_memories(), (original,))

    def test_untrusted_store_cannot_leak_foreign_owner_memory(self):
        class LeakyStore(AvaMemory):
            def list_for_owner(self, owner_id):
                # Simulate an incorrectly scoped external persistence adapter.
                return tuple(self._items.values())

        store = LeakyStore()
        first = Ava(owner_id="owner-1", brain=self.brain, memory=store)
        second = Ava(owner_id="owner-2", brain=self.brain, memory=store)
        first.remember("private-owner-one", consent=True)
        second.remember("private-owner-two", consent=True)
        self.assertEqual(len(first.list_memories()), 1)
        self.assertEqual(len(first.export_memories(consent=True)), 1)
        first.converse("سلام", use_memories=True)
        self.assertNotIn("private-owner-two", str(self.calls[-1]))
        self.assertIn("private-owner-one", str(self.calls[-1]))

    def test_brain_failure_does_not_create_memory_or_external_receipt(self):
        def failing_brain(messages):
            raise RuntimeError("provider unavailable")

        assistant = Ava(owner_id="owner-1", brain=failing_brain, memory=self.shared_store)
        with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
            assistant.converse("سلام", use_memories=True)
        self.assertEqual(assistant.list_memories(), ())
        self.assertEqual(self.shared_store.list_for_owner("owner-1"), ())

    def test_non_string_brain_response_fails_closed(self):
        assistant = Ava(owner_id="owner-1", brain=lambda messages: None)
        with self.assertRaisesRegex(TypeError, "Brain must return a string"):
            assistant.converse("سلام")
        self.assertEqual(assistant.list_memories(), ())

    def test_empty_model_reply_is_rejected_without_memory_writes(self):
        for reply in ("", "  ", "\n\t"):
            with self.subTest(reply=repr(reply)):
                assistant = Ava(owner_id="owner-1", brain=lambda messages, value=reply: value)
                with self.assertRaisesRegex(ValueError, "empty response"):
                    assistant.converse("سلام")
                self.assertEqual(assistant.list_memories(), ())

    def test_reply_and_validation(self):
        self.assertEqual(self.ava.converse("سلام").text, "درود مجتبی جان")
        with self.assertRaises(ValueError):
            self.ava.converse("  ")
        with self.assertRaises(ValueError):
            Ava(owner_id=" ", brain=self.brain)


if __name__ == "__main__":
    unittest.main()
