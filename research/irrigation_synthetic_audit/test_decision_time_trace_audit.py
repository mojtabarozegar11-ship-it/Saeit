"""Synthetic fixtures only: no real forecast, farm or economic observations."""
from copy import deepcopy
import unittest

from .decision_time_trace_audit import TraceError, audit_trace

def example(policy="baseline"):
    return dict(
        scenario_id="scenario_1", path_id="dry_1", policy=policy,
        decision_at="2026-06-01T08:00:00Z",
        forecast_issued_at="2026-06-01T07:00:00Z",
        forecast_valid_at="2026-06-01T12:00:00Z",
        rainfall_observed_at="2026-06-01T13:00:00Z",
        forecast_rain_mm="2.5", realized_rain_mm="3.0",
        rainfall_input_kind="issued_forecast",
    )

class ExAnteTraceTests(unittest.TestCase):
    def test_two_policies_same_information(self):
        report = audit_trace([example(), example("alternative")])
        self.assertEqual(report["rows_checked"], 2)
        self.assertEqual(report["matched_scenario_paths"], 1)
        self.assertFalse(report["source_timestamps_authenticated"])
        self.assertFalse(report["field_efficacy_verified"])

    def test_observed_before_decision_is_structurally_allowed(self):
        row = example()
        row["rainfall_input_kind"] = "realized_observation"
        row["rainfall_observed_at"] = "2026-06-01T07:30:00Z"
        self.assertTrue(audit_trace([row])["structural_checks_passed"])

    def test_reject_empty(self):
        with self.assertRaises(TraceError): audit_trace([])

    def test_reject_non_list(self):
        with self.assertRaises(TraceError): audit_trace({})

    def test_reject_duplicate_policy(self):
        with self.assertRaises(TraceError): audit_trace([example(), example()])

    def test_reject_missing_field(self):
        row = example(); del row["decision_at"]
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_extra_field(self):
        row = example(); row["payment"] = "paid"
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_future_forecast_issue(self):
        row = example(); row["forecast_issued_at"] = "2026-06-01T09:00:00Z"
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_forecast_valid_before_issue(self):
        row = example(); row["forecast_valid_at"] = "2026-06-01T06:00:00Z"
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_future_realized_rain_leakage(self):
        row = example(); row["rainfall_input_kind"] = "realized_observation"
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_policy_different_decision_time(self):
        row = example("alternative"); row["decision_at"] = "2026-06-01T08:01:00Z"
        with self.assertRaises(TraceError): audit_trace([example(), row])

    def test_reject_policy_different_forecast_issue(self):
        row = example("alternative"); row["forecast_issued_at"] = "2026-06-01T06:00:00Z"
        with self.assertRaises(TraceError): audit_trace([example(), row])

    def test_reject_policy_different_forecast_validity(self):
        row = example("alternative"); row["forecast_valid_at"] = "2026-06-01T11:00:00Z"
        with self.assertRaises(TraceError): audit_trace([example(), row])

    def test_reject_policy_different_forecast_amount(self):
        row = example("alternative"); row["forecast_rain_mm"] = "3.5"
        with self.assertRaises(TraceError): audit_trace([example(), row])

    def test_reject_policy_different_information_type(self):
        row = example("alternative"); row["rainfall_input_kind"] = "realized_observation"
        row["rainfall_observed_at"] = "2026-06-01T07:30:00Z"
        with self.assertRaises(TraceError): audit_trace([example(), row])

    def test_reject_unknown_rainfall_kind(self):
        row = example(); row["rainfall_input_kind"] = "oracle"
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_negative_rainfall(self):
        row = example(); row["realized_rain_mm"] = "-1"
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_noncanonical_rainfall(self):
        row = example(); row["forecast_rain_mm"] = "01.2"
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_nan_rainfall(self):
        row = example(); row["forecast_rain_mm"] = "NaN"
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_float_rainfall(self):
        row = example(); row["forecast_rain_mm"] = 2.5
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_naive_timestamp(self):
        row = example(); row["decision_at"] = "2026-06-01T08:00:00"
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_invalid_timestamp(self):
        row = example(); row["decision_at"] = "2026-13-01T08:00:00Z"
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_injected_identifier(self):
        row = example(); row["policy"] = "../baseline"
        with self.assertRaises(TraceError): audit_trace([row])

    def test_reject_nonstring_identifier(self):
        row = example(); row["path_id"] = 1
        with self.assertRaises(TraceError): audit_trace([row])

    def test_separate_paths_not_mistaken_for_same_pair(self):
        row = example("alternative"); row["path_id"] = "wet_2"
        self.assertEqual(audit_trace([example(), row])["matched_scenario_paths"], 2)

if __name__ == "__main__":
    unittest.main()
