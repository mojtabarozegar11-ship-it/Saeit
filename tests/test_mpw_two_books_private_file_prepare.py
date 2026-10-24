"""Unit tests for non-destructive book asset staging: no network or Django needed."""
import hashlib
import importlib.util
import os
from pathlib import Path

import pytest

MODFILE = Path(__file__).resolve().parents[1] / "scripts" / "mpw_two_books_private_file_prepare.py"
spec = importlib.util.spec_from_file_location("mpw_book_stage", MODFILE)
book = importlib.util.module_from_spec(spec)
spec.loader.exec_module(book)


def make_pdf(path):
    payload = b"%PDF-1.6\n" + b"x" * 2400 + b"\n%%EOF\n"
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def test_verified_private_copy_preserves_source_and_denies_overwrite(tmp_path):
    source = tmp_path / "book-original.pdf"
    digest = make_pdf(source)
    prior = source.read_bytes()
    dest = tmp_path / "private" / "72.pdf"
    assert book.copy_verified(source, dest, digest) is True
    assert source.read_bytes() == prior
    assert dest.read_bytes() == prior
    assert dest.stat().st_mode & 0o077 == 0
    assert book.copy_verified(source, dest, digest) is False
    assert sorted(x.name for x in dest.parent.iterdir()) == ["72.pdf"]


def test_corruption_and_wrong_hash_are_never_accepted(tmp_path):
    source = tmp_path / "source.pdf"
    digest = make_pdf(source)
    dest = tmp_path / "dst" / "225.pdf"
    with pytest.raises(RuntimeError, match="hash mismatch"):
        book.copy_verified(source, dest, "a" * 64)
    assert not dest.exists()
    assert book.copy_verified(source, dest, digest) is True
    dest.write_bytes(b"not a real PDF")
    with pytest.raises(RuntimeError):
        book.copy_verified(source, dest, digest)


def test_private_copy_refuses_symlink_target(tmp_path):
    source = tmp_path / "source.pdf"
    digest = make_pdf(source)
    dest = tmp_path / "linked.pdf"
    dest.symlink_to(source)
    with pytest.raises(RuntimeError, match="symlink"):
        book.copy_verified(source, dest, digest)


def test_expected_fingerprint_and_sale_hold():
    assert set(book.PILOTS) == {72, 225}
    assert book.PILOTS[72]["price"] == "7.50"
    assert book.PILOTS[225]["price"] == "4.00"
    for pilot in book.PILOTS.values():
        assert len(pilot["sha"]) == 64


def test_source_pdf_not_replaced_when_corrupt(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_text("bogus pdf")
    with pytest.raises(RuntimeError):
        book.verify_pdf(source, "0" * 64)
