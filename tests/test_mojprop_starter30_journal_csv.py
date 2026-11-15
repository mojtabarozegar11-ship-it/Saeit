"""Customer journal CSV round-trip and malicious input regression tests."""
import unittest
from scripts.mojprop_starter30 import InvalidJournal
from scripts.mojprop_starter30_journal_csv import (
    COLUMNS, MAX_BYTES, empty_journal_csv, parse_journal_csv, assess_csv
)


def valid_csv():
    header = ",".join(COLUMNS) + "\n"
    return (header + "".join(f"{i},100.00,yes,yes\n" for i in range(1, 11))).encode("utf-8")


class Starter30JournalCSVTests(unittest.TestCase):
    def test_uncompleted_template_never_suggests_real_results(self):
        data = empty_journal_csv()
        self.assertEqual(len(data.splitlines()), 11)
        self.assertIn("1,,,", data)
        self.assertNotIn("100.00", data)

    def test_valid_ten_session_csv(self):
        result = assess_csv(valid_csv())
        self.assertEqual(result["status"], "completed_educational_review")
        self.assertEqual(result["sessions_recorded"], 10)
        self.assertIs(result["payment_recorded"], False)

    def test_utf8_bom_accepted(self):
        self.assertEqual(len(parse_journal_csv(b"\xef\xbb\xbf" + valid_csv())), 10)

    def test_crlf_accepted(self):
        self.assertEqual(len(parse_journal_csv(valid_csv().replace(b"\n", b"\r\n"))), 10)

    def test_bad_header_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(valid_csv().replace(b"closing_equity_usd", b"wallet_address"))

    def test_injection_field_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(valid_csv().replace(b"100.00", b"=1+1", 1))

    def test_buyer_email_additional_field_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(valid_csv().replace(b"1,100.00,yes,yes", b"1,100.00,yes,yes,buyer@example.org", 1))

    def test_duplicate_session_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(valid_csv().replace(b"2,100.00,yes,yes", b"1,100.00,yes,yes", 1))

    def test_missing_yesno_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(valid_csv().replace(b"3,100.00,yes,yes", b"3,100.00,,yes", 1))

    def test_empty_document_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(b"")

    def test_invalid_utf8_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(b"\xff\xfe\xfa")

    def test_oversized_document_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(b"A" * (MAX_BYTES + 1))

    def test_unfinished_template_is_not_passed(self):
        with self.assertRaises(InvalidJournal):
            assess_csv(empty_journal_csv().encode("utf-8"))

    def test_extra_row_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(valid_csv() + b"11,100.00,yes,yes\n")

    def test_blank_line_within_csv_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(valid_csv().replace(b"5,100.00,yes,yes\n", b"\n5,100.00,yes,yes\n", 1))

    def test_string_instead_of_bytes_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(valid_csv().decode())

    def test_unexpected_carriage_return_refused(self):
        with self.assertRaises(InvalidJournal):
            parse_journal_csv(valid_csv().replace(b"100.00", b"100.\r00", 1))

    def test_incomplete_eight_sessions_are_not_certified(self):
        rows = valid_csv().decode().splitlines()
        result = assess_csv(("\n".join(rows[:9]) + "\n").encode())
        self.assertEqual(result["status"], "incomplete_training")


if __name__ == "__main__":
    unittest.main()
