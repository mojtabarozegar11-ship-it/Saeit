"""Regression checks for optional, owner-isolated encrypted AVA memory."""

import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest

from ava_core import AvaRuntime, ConsentError, GoalProposal
from ava_core.core import MemoryItem
from ava_core.storage import EncryptedSQLiteMemory, MemoryIntegrityError, MemoryKeyError


class EncryptedStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ava-memory.sqlite3"
        self.key = b"k" * 32

    def open_store(self, key=None):
        return EncryptedSQLiteMemory(self.path, key=self.key if key is None else key)

    def test_owner_consent_and_end_to_end_reopen(self):
        with self.open_store() as store:
            runtime = AvaRuntime(
                owner_id="mojtaba", brain=lambda messages: messages[-1]["content"],
                propose_goals=lambda _: (), memory=store,
            )
            with self.assertRaises(ConsentError):
                runtime.remember("اطلاعات شخصی")
            item = runtime.remember("اطلاعات شخصی", consent=True)
            turn = runtime.converse("درود", use_memories=True)
            self.assertEqual(turn.reply.memories_used, 1)
            self.assertEqual(runtime.status().memory_items, 1)

        with self.open_store() as reopened:
            self.assertEqual(reopened.list_for_owner("mojtaba"), (item,))
            runtime = AvaRuntime(
                owner_id="mojtaba", brain=lambda messages: str(messages),
                propose_goals=lambda _: (), memory=reopened,
            )
            self.assertIn("اطلاعات شخصی", runtime.converse("سلام", use_memories=True).reply.text)
            self.assertTrue(runtime.forget(item.id))
        with self.open_store() as reopened:
            self.assertEqual(reopened.list_for_owner("mojtaba"), ())

    def test_default_runtime_memory_is_still_ephemeral(self):
        runtime = AvaRuntime(
            owner_id="mojtaba", brain=lambda _: "سلام", propose_goals=lambda _: (),
        )
        runtime.remember("Only RAM", consent=True)
        self.assertEqual(runtime.status().memory_items, 1)
        self.assertFalse(self.path.exists())

    def test_ciphertext_and_owner_name_are_not_plaintext_on_disk(self):
        secret = "distinct-private-note-7f9e44c2"
        with self.open_store() as store:
            store.add(MemoryItem("memo-1", "very-private-owner", secret, "2026-11-11T01:00:00Z"))
        data = self.path.read_bytes()
        self.assertNotIn(secret.encode(), data)
        self.assertNotIn(b"very-private-owner", data)

    def test_new_database_is_private_file(self):
        with self.open_store():
            self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_existing_world_readable_file_is_refused(self):
        self.path.touch(mode=0o600)
        os.chmod(self.path, 0o644)
        with self.assertRaises(PermissionError):
            self.open_store()

    def test_symlink_file_is_refused(self):
        original = Path(self.temp.name) / "original.db"
        original.touch()
        self.path.symlink_to(original)
        with self.assertRaises(PermissionError):
            self.open_store()

    def test_two_owners_cannot_see_or_delete_each_others_memories(self):
        with self.open_store() as store:
            store.add(MemoryItem("one", "first", "A", "time-a"))
            store.add(MemoryItem("two", "second", "B", "time-b"))
            self.assertEqual([i.text for i in store.list_for_owner("first")], ["A"])
            self.assertEqual([i.text for i in store.list_for_owner("second")], ["B"])
            self.assertFalse(store.delete("first", "two"))
            self.assertEqual(len(store.list_for_owner("second")), 1)

    def test_unknown_owner_cannot_read_memory(self):
        with self.open_store() as store:
            store.add(MemoryItem("one", "first", "A", "time"))
            self.assertEqual(store.list_for_owner("unknown"), ())

    def test_wrong_key_is_rejected_instead_of_silent_empty_memory(self):
        with self.open_store() as store:
            store.add(MemoryItem("one", "first", "A", "time"))
        with self.assertRaises(MemoryKeyError):
            self.open_store(key=b"w" * 32)

    def test_key_material_must_be_32_bytes(self):
        for key in ("string", b"short", b"a" * 31, b"b" * 33):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.open_store(key=key)

    def test_modified_ciphertext_is_detected(self):
        with self.open_store() as store:
            store.add(MemoryItem("one", "first", "secret", "time"))
            with sqlite3.connect(self.path) as db:
                db.execute("UPDATE memory SET ciphertext=? WHERE id=?", (b"tampered", "one"))
            with self.assertRaises(MemoryIntegrityError):
                store.list_for_owner("first")

    def test_modified_authenticated_metadata_is_detected(self):
        with self.open_store() as store:
            store.add(MemoryItem("one", "first", "secret", "time"))
            with sqlite3.connect(self.path) as db:
                db.execute("UPDATE memory SET created_at=? WHERE id=?", ("changed", "one"))
            with self.assertRaises(MemoryIntegrityError):
                store.list_for_owner("first")

    def test_modified_key_verifier_is_detected(self):
        with self.open_store():
            pass
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE key_check SET ciphertext=? WHERE id=1", (b"invalid",))
        with self.assertRaises(MemoryKeyError):
            self.open_store()

    def test_duplicate_id_is_rejected_without_overwriting_previous_memory(self):
        with self.open_store() as store:
            store.add(MemoryItem("one", "first", "original", "time"))
            with self.assertRaises(sqlite3.IntegrityError):
                store.add(MemoryItem("one", "first", "replacement", "time2"))
            self.assertEqual(store.list_for_owner("first")[0].text, "original")

    def test_empty_or_invalid_memory_is_rejected(self):
        with self.open_store() as store:
            with self.assertRaises(ValueError):
                store.add(MemoryItem("one", "first", "  ", "time"))
            with self.assertRaises(ValueError):
                store.add(MemoryItem("", "first", "text", "time"))
            with self.assertRaises(ValueError):
                store.list_for_owner("")


if __name__ == "__main__":
    unittest.main()
