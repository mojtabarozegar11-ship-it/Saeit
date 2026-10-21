"""Four real production origins; defect -> rework -> retest; never discard."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import AgentTask, Order, Product
from core.mojplaywin_production_models import (
    MojPlayWinManufacturingOrder as Brief,
    MojPlayWinQAReview as Review,
    MojPlayWinQADefect as Defect,
    MojPlayWinReworkCycle as Rework,
)
from core.mojplaywin_quality_loop import (
    ProductionFlowError, create_non_site_brief, document_defect_fix,
    record_artifact_for_qa, record_quality_review, start_rework,
    submit_rework_for_retest,
)


def bad_math():
    return [{
        "defect_code": "MATH-001",
        "severity": "major",
        "cause": "Gross margin uses revenue rather than gross profit",
        "expected": "Gross margin = (revenue - costs) / revenue",
        "actual": "Original file uses revenue / costs",
        "correction_plan": "Correct the formula and rerun boundary-case tests",
    }]


class FourSourcesAndQualityLoopTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="mpw_owner_quality", email="owner@example.test", password="test-password"
        )
        self.inspector = get_user_model().objects.create_user(
            username="quality_inspector", email="qa@example.test", password="test-password", is_staff=True
        )

    def _brief(self, origin="invention", reference="RND-0001"):
        brief, created = create_non_site_brief(
            origin=origin, reference=reference,
            description="Documented problem and proposed validation steps",
            product_title="Original Calculations Workbook",
            file_format="xlsx+pdf",
            deliverable="Editable tested workbook and user guide",
            owner=self.owner,
        )
        self.assertTrue(created)
        return brief

    def _scoped(self, brief):
        brief.status = "scoped"
        brief.review_note = "Owner-scoped, no sale or VPS dispatch authorized."
        brief.full_clean()
        brief.save()

    def _enter_qa(self, brief, n):
        return record_artifact_for_qa(
            brief_id=brief.id, operator=self.owner,
            artifact_reference="artifact-version-%s" % n,
            production_evidence="Manually entered reference; not proof of VPS execution",
        )

    def test_all_four_origins_without_fabricated_customer_order(self):
        from django.core.management import call_command
        call_command("mojplaywin_sync_production_bank", apply=True, site="mojplaywin.com", stdout=StringIO())
        for name, ref in (("customer", "CUSTOMER-REQUEST-001"), ("market", "MARKET-RESEARCH-001"), ("invention", "RND-HYPOTHESIS-001")):
            self._brief(name, ref)
        self.assertEqual(Brief.objects.filter(origin_type="site").count(), 24)
        for name in ("customer", "market", "invention"):
            self.assertEqual(Brief.objects.filter(origin_type=name).count(), 1)
            self.assertFalse(Brief.objects.get(origin_type=name).signal_id)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(AgentTask.objects.count(), 0)

    def test_create_request_is_idempotent_but_not_a_sale(self):
        brief = self._brief("customer", "CUSTOMER-REQUEST-002")
        again, created = create_non_site_brief(
            origin="customer", reference="CUSTOMER-REQUEST-002",
            description="Documented problem and proposed validation steps",
            product_title="Original Calculations Workbook", file_format="xlsx+pdf",
            deliverable="Editable tested workbook and user guide",
            owner=self.owner,
        )
        self.assertFalse(created)
        self.assertEqual(brief.pk, again.pk)
        self.assertEqual(Brief.objects.count(), 1)
        with self.assertRaises(ProductionFlowError):
            self._brief("market", "CUSTOMER-REQUEST-002")

    def test_missing_source_evidence_fails_closed(self):
        with self.assertRaises(ProductionFlowError):
            create_non_site_brief(
                origin="market", reference="", description="",
                product_title="Example", file_format="pdf", deliverable="Document",
                owner=self.owner,
            )
        self.assertFalse(Brief.objects.exists())

    def test_failed_quality_always_creates_diagnosis_and_rework(self):
        brief = self._brief()
        self._scoped(brief)
        self._enter_qa(brief, "v1")
        review = record_quality_review(
            brief_id=brief.id, inspector=self.inspector, review_key="qa-fail-v1",
            artifact_reference="artifact-version-v1", summary="Validated margin formula and reproduced incorrect result",
            verdict="fail", defects=bad_math(),
        )
        brief.refresh_from_db()
        self.assertEqual(brief.production_stage, "rework_required")
        self.assertEqual(brief.quality_round, 1)
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(Defect.objects.count(), 1)
        self.assertEqual(Rework.objects.count(), 1)
        self.assertEqual(review.rework_cycle.state, "queued")
        self.assertTrue(Brief.objects.filter(pk=brief.pk).exists())
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)

    def test_rework_requires_correction_evidence_and_independent_retest(self):
        brief = self._brief()
        self._scoped(brief)
        self._enter_qa(brief, "v1")
        failure = record_quality_review(
            brief_id=brief.id, inspector=self.inspector, review_key="qa1",
            artifact_reference="artifact-version-v1", summary="Numerical acceptance test failed",
            verdict="fail", defects=bad_math(),
        )
        with self.assertRaises(ProductionFlowError):
            record_quality_review(
                brief_id=brief.id, inspector=self.inspector, review_key="premature-pass",
                artifact_reference="artifact-version-v1", summary="Bypassed test",
                verdict="pass",
            )
        cycle = start_rework(cycle_id=failure.rework_cycle.id, operator=self.owner)
        with self.assertRaises(ProductionFlowError):
            submit_rework_for_retest(
                cycle_id=cycle.id, operator=self.owner,
                updated_artifact_reference="artifact-version-v2",
                repair_summary="Formula corrected",
            )
        defect = failure.defects.get()
        document_defect_fix(
            defect_id=defect.id, operator=self.owner,
            correction_evidence="Corrected workbook formula with recorded sample-case outputs",
        )
        with self.assertRaises(ProductionFlowError):
            submit_rework_for_retest(
                cycle_id=cycle.id, operator=self.owner,
                updated_artifact_reference="artifact-version-v1",
                repair_summary="Formula corrected",
            )
        submit_rework_for_retest(
            cycle_id=cycle.id, operator=self.owner,
            updated_artifact_reference="artifact-version-v2",
            repair_summary="Replaced formula and regenerated workbook, needs retest",
        )
        review = record_quality_review(
            brief_id=brief.id, inspector=self.inspector, review_key="qa2",
            artifact_reference="artifact-version-v2", summary="Reran margin acceptance and boundary tests",
            verdict="pass",
        )
        brief.refresh_from_db()
        self.assertEqual(brief.production_stage, "qa_passed")
        self.assertEqual(brief.quality_round, 2)
        self.assertEqual(review.verdict, "pass")
        self.assertEqual(Review.objects.count(), 2)
        self.assertEqual(Rework.objects.count(), 1)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)

    def test_failure_without_root_cause_never_disappears(self):
        brief = self._brief()
        self._scoped(brief)
        self._enter_qa(brief, "v1")
        with self.assertRaises(ProductionFlowError):
            record_quality_review(
                brief_id=brief.pk, inspector=self.inspector, review_key="empty-defects",
                artifact_reference="artifact-version-v1", summary="Something failed",
                verdict="fail", defects=[],
            )
        self.assertEqual(Review.objects.count(), 0)
        brief.refresh_from_db()
        self.assertEqual(brief.production_stage, "qa_review")

    def test_three_failures_trigger_expert_attention_not_discard(self):
        brief = self._brief()
        self._scoped(brief)
        self._enter_qa(brief, "v1")
        for n in range(1, 4):
            failed = record_quality_review(
                brief_id=brief.pk, inspector=self.inspector, review_key="review-%s" % n,
                artifact_reference="artifact-version-v%s" % n,
                summary="Documented reproducible failure number %s" % n,
                verdict="fail", defects=bad_math(),
            )
            brief.refresh_from_db()
            if n == 3:
                self.assertEqual(brief.production_stage, "attention_required")
                self.assertEqual(failed.rework_cycle.state, "needs_expert")
                with self.assertRaises(ProductionFlowError):
                    start_rework(cycle_id=failed.rework_cycle.id, operator=self.inspector)
            else:
                self.assertEqual(brief.production_stage, "rework_required")
                start_rework(cycle_id=failed.rework_cycle.id, operator=self.owner)
                document_defect_fix(
                    defect_id=failed.defects.get().id, operator=self.owner,
                    correction_evidence="Changes and tests documented for revision %s" % n,
                )
                submit_rework_for_retest(
                    cycle_id=failed.rework_cycle.id, operator=self.owner,
                    updated_artifact_reference="artifact-version-v%s" % (n + 1),
                    repair_summary="Updated design and QA handoff %s" % n,
                )
        self.assertEqual(Review.objects.count(), 3)
        self.assertEqual(Rework.objects.count(), 3)
        self.assertEqual(Defect.objects.count(), 3)
        self.assertTrue(Brief.objects.filter(pk=brief.pk).exists())
        self.assertEqual(Product.objects.count(), 0)

    def test_quality_retries_are_idempotent(self):
        brief = self._brief()
        self._scoped(brief)
        self._enter_qa(brief, "v1")
        first = record_quality_review(
            brief_id=brief.id, inspector=self.inspector, review_key="same-inspection",
            artifact_reference="artifact-version-v1", summary="Repeatable failure",
            verdict="fail", defects=bad_math(),
        )
        second = record_quality_review(
            brief_id=brief.id, inspector=self.inspector, review_key="same-inspection",
            artifact_reference="artifact-version-v1", summary="Repeatable failure",
            verdict="fail", defects=bad_math(),
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Rework.objects.count(), 1)

    def test_same_reference_cannot_switch_qa_verdict(self):
        brief = self._brief()
        self._scoped(brief)
        self._enter_qa(brief, "v1")
        record_quality_review(
            brief_id=brief.pk, inspector=self.inspector, review_key="same-ref",
            artifact_reference="artifact-version-v1", summary="Original reproducible result",
            verdict="fail", defects=bad_math(),
        )
        with self.assertRaises(ProductionFlowError):
            record_quality_review(
                brief_id=brief.pk, inspector=self.inspector, review_key="same-ref",
                artifact_reference="artifact-version-v1", summary="Trying to overwrite failure",
                verdict="pass",
            )
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(Review.objects.get().verdict, "fail")
