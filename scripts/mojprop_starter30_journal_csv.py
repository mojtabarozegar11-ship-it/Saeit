"""Bounded, deterministic CSV import for Starter30 educational journals.

No uploads, user accounts, personal information, database or paid entitlement.
Only the exact ten-session numeric schema can reach the assessment engine.
"""
from __future__ import annotations
import csv
import io
from scripts.mojprop_starter30 import assess_journal, InvalidJournal

MAX_BYTES = 4096
COLUMNS = ("session", "closing_equity_usd", "risk_plan_recorded", "reflection_recorded")
YES_NO = {"yes": True, "no": False}


def empty_journal_csv() -> str:
    """Return a buyer-fillable CSV, without fabricated completed performance."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(COLUMNS)
    for index in range(1, 11):
        writer.writerow([index, "", "", ""])
    return output.getvalue()


def parse_journal_csv(content: bytes) -> list[dict]:
    if type(content) is not bytes or len(content) > MAX_BYTES:
        raise InvalidJournal("Only a CSV file no larger than 4096 bytes is accepted")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidJournal("CSV must use UTF-8") from exc
    if "\x00" in text or "\r" in text.replace("\r\n", ""):
        raise InvalidJournal("Invalid CSV newline or control")
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader)
        if tuple(header) != COLUMNS:
            raise InvalidJournal("CSV header does not match the educational journal contract")
        rows = []
        for fields in reader:
            if len(rows) >= 10 or len(fields) != 4:
                raise InvalidJournal("CSV must contain one to ten complete sessions")
            if any(("\n" in field or "\r" in field or "\x00" in field) for field in fields):
                raise InvalidJournal("Multiline or control characters are not allowed")
            position, equity, risk, reflection = fields
            if position != str(len(rows) + 1) or risk not in YES_NO or reflection not in YES_NO:
                raise InvalidJournal("Session identifiers and yes/no flags must be exact")
            rows.append({
                "session": len(rows) + 1,
                "closing_equity_usd": equity,
                "risk_plan_recorded": YES_NO[risk],
                "reflection_recorded": YES_NO[reflection],
            })
    except (csv.Error, StopIteration) as exc:
        raise InvalidJournal("Invalid CSV structure") from exc
    assess_journal(rows)  # Validation, never a settlement or eligibility decision.
    return rows


def assess_csv(content: bytes) -> dict:
    return assess_journal(parse_journal_csv(content))
