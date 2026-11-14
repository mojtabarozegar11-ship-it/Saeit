"""Offline pagination regressions; no Django, real orders, mail or funds."""
import unittest
from core.tron_gateway_catalog import (
    CatalogueScanLimit, PAGE_SIZE, MAX_CATALOG_SCANNED, paginate_eligible,
)


class EligibleCataloguePaginationTests(unittest.TestCase):
    def approve(self, row):
        return row if row > 0 else None

    def test_trailing_ineligible_rows_do_not_create_phantom_page(self):
        items, more = paginate_eligible([1] * PAGE_SIZE + [0] * 90,
                                        self.approve, page=1)
        self.assertEqual(len(items), 50)
        self.assertFalse(more)

    def test_later_eligible_row_is_not_hidden_behind_ineligible_first_fifty(self):
        items, more = paginate_eligible([0] * 70 + [9], self.approve, page=1)
        self.assertEqual(items, [9])
        self.assertFalse(more)

    def test_second_page_contains_only_remaining_eligible_results(self):
        src = [0] * 20 + list(range(1, 56)) + [0] * 20
        first, more = paginate_eligible(src, self.approve, page=1)
        second, final = paginate_eligible(src, self.approve, page=2)
        self.assertEqual(first, list(range(1, 51)))
        self.assertEqual(second, list(range(51, 56)))
        self.assertTrue(more)
        self.assertFalse(final)

    def test_lookahead_does_not_drop_fifty_first_eligible_product(self):
        items, more = paginate_eligible(range(1, 52), self.approve, page=1)
        self.assertEqual(items[-1], 50)
        self.assertTrue(more)
        next_items, _ = paginate_eligible(range(1, 52), self.approve, page=2)
        self.assertEqual(next_items, [51])

    def test_all_ineligible_is_empty_and_final(self):
        items, more = paginate_eligible([0] * 99, self.approve, page=1)
        self.assertEqual(items, [])
        self.assertFalse(more)

    def test_empty_source_is_empty_and_final(self):
        self.assertEqual(paginate_eligible([], self.approve, page=1), ([], False))

    def test_no_preloading_a_long_stream(self):
        seen = []
        def stream():
            for number in range(1, 100000):
                seen.append(number)
                yield number
        page, has_more = paginate_eligible(stream(), self.approve, page=1)
        self.assertEqual(len(page), 50)
        self.assertTrue(has_more)
        self.assertEqual(len(seen), 51)

    def test_eligible_start_page_one_hundred(self):
        src = range(1, 5001)
        items, more = paginate_eligible(src, self.approve, page=100)
        self.assertEqual(items, list(range(4951, 5001)))
        self.assertFalse(more)

    def test_exact_scan_bound_allowed(self):
        items, more = paginate_eligible([0] * (MAX_CATALOG_SCANNED - 1) + [1],
                                        self.approve, page=1)
        self.assertEqual(items, [1])
        self.assertFalse(more)

    def test_scan_bound_fail_closed(self):
        with self.assertRaises(CatalogueScanLimit):
            paginate_eligible([0] * (MAX_CATALOG_SCANNED + 1),
                              self.approve, page=1)

    def test_no_bool_page(self):
        with self.assertRaises(ValueError):
            paginate_eligible([1], self.approve, page=True)

    def test_non_integral_and_overlarge_page_denied(self):
        for page in (0, -1, 101, 1.0, "1", None):
            with self.subTest(page=page), self.assertRaises(ValueError):
                paginate_eligible([1], self.approve, page=page)

    def test_scan_limit_does_not_depend_on_eligibility(self):
        with self.assertRaises(CatalogueScanLimit):
            paginate_eligible([0] * MAX_CATALOG_SCANNED + [1],
                              self.approve, page=1)

    def test_side_effect_free_approve_evaluated_once_per_scanned_product(self):
        calls = []
        def approve(row):
            calls.append(row)
            return row if row % 2 else None
        items, more = paginate_eligible(range(1, 105), approve, page=1)
        self.assertEqual(items, list(range(1, 100, 2)))
        self.assertTrue(more)
        self.assertEqual(len(calls), 101)


if __name__ == "__main__":
    unittest.main()
