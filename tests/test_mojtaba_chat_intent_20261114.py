"""Pure deterministic command and consent regressions. No DB, network or external side effects."""
import json
import unittest
from dataclasses import replace
from types import SimpleNamespace
from core.operation_planner import plan_chat_operation, approval_reason, valid_draft_path
from core.chat_operation_security import is_authorized_chat_operator

CASES = json.loads(r'''[["deploy","deploy release now","cpanel.deploy_release","cPanel",null],["deployFa","انتشار سایت را اجرا کن","cpanel.deploy_release","cPanel",null],["deployQuestion","Why deploy release now?",null,null,null],["deployMention","Explain deploy release now",null,null,null],["preflight","cpanel preflight","cpanel.preflight","cPanel",null],["preflightQuestion","cpanel preflight?",null,null,null],["passenger","passenger inventory","cpanel.passenger_inventory","cPanel",null],["passengerFa","فهرست passenger","cpanel.passenger_inventory","cPanel",null],["passengerQuestion","فهرست passenger؟",null,null,null],["createMPW","create page /offers/Today \"Offer\" for mojplaywin.com","site.create_draft_page","mojplaywin","/offers/Today"],["createZomorod","صفحه جدید /company/services «خدمات» سایت زمرد","site.create_draft_page","zomorodmelal","/company/services"],["editMPW","edit page /offers/Today for mojplaywin.com","site.update_draft_page","mojplaywin","/offers/Today"],["editZomorod","ویرایش صفحه /company/news سایت زمرد","site.update_draft_page","zomorodmelal","/company/news"],["noTarget","create page /offers \"Offer\"",null,null,null],["twoTargets","create page /offers \"Offer\" for mojplaywin.com and zomorodmelal.ir",null,null,null],["brandOnlyInTitle","create page /offers \"mojplaywin.com\" for zomorodmelal.ir",null,null,null],["titleOtherSite","create page /offers \"zomorodmelal.ir\" for mojplaywin.com","site.create_draft_page","mojplaywin","/offers"],["titlePath","create page /offers \"Website /sample\" for mojplaywin.com","site.create_draft_page","mojplaywin","/offers"],["missingTitle","create page /offers Offer for mojplaywin.com",null,null,null],["multipleTitles","create page /offers \"Title1\" \"Title2\" for mojplaywin.com",null,null,null],["emptyTitle","create page /offers \"   \" for mojplaywin.com",null,null,null],["markupTitle","create page /offers \"<script>\" for mojplaywin.com",null,null,null],["englishNegation","do not create page /offers \"Offer\" for mojplaywin.com",null,null,null],["persianNegation","صفحه جدید /company/test «تست» سایت زمرد نساز",null,null,null],["cancel","create page /offers \"Offer\" for mojplaywin.com cancel",null,null,null],["question","create page /offers \"Offer\" for mojplaywin.com?",null,null,null],["secondVerb","create page /offers \"Offer\" for mojplaywin.com then edit page /offers",null,null,null],["twoPaths","create page /offers /extra \"Offer\" for mojplaywin.com",null,null,null],["root","create page / \"Offer\" for mojplaywin.com",null,null,null],["traversal","create page /company/../secret \"Offer\" for zomorodmelal.ir",null,null,null],["encoded","create page /company/%2e%2e/x \"Offer\" for zomorodmelal.ir",null,null,null],["doubleSlash","create page //offers \"Offer\" for mojplaywin.com",null,null,null],["dotSegment","create page /company/./secret \"Offer\" for zomorodmelal.ir",null,null,null],["wrongRoot","create page /offers \"Offer\" for zomorodmelal.ir",null,null,null],["fragment","create page /offers#frag \"Offer\" for mojplaywin.com",null,null,null],["query","create page /offers?token=x \"Offer\" for mojplaywin.com",null,null,null],["unicodePath","create page /فارسی \"Offer\" for mojplaywin.com",null,null,null],["newline","create page /offers \"Offer\" for mojplaywin.com\nanother line",null,null,null],["bidi","create page /offers \"Offer\" for mojplaywin.com‮",null,null,null],["oversize","create page /offers \"Offer\" for mojplaywin.comxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",null,null,null],["casePreserved","create page /Services/Farm2026 \"Farm\" for mojplaywin.com","site.create_draft_page","mojplaywin","/Services/Farm2026"],["ordinary","Can you discuss farming economics?",null,null,null]]''')


class PlannerCases(unittest.TestCase):
    pass


def make_case(item):
    name, text, action, target, path = item
    def check(self):
        result = plan_chat_operation(text)
        if action is None:
            self.assertIsNone(result, msg=name)
        else:
            self.assertIsNotNone(result, msg=name)
            self.assertEqual(result.action, action, msg=name)
            self.assertEqual(result.target, target, msg=name)
            self.assertTrue(result.approval_required)
            if path is not None:
                self.assertEqual(result.parameters["path"], path, msg=name)
    return check

for i, case in enumerate(CASES, 1):
    setattr(PlannerCases, "test_%02d_%s" % (i, case[0]), make_case(case))


class ReasonAndIdentityCases(unittest.TestCase):
    def setUp(self):
        self.operation = plan_chat_operation('create page /offers "Offer" for mojplaywin.com')
        self.assertIsNotNone(self.operation)

    def test_reason_binds_exact_session(self):
        self.assertEqual(json.loads(approval_reason(self.operation, session_id=17))["session_id"], 17)

    def test_missing_session_denied(self):
        with self.assertRaises(ValueError): approval_reason(self.operation)

    def test_boolean_session_denied(self):
        with self.assertRaises(ValueError): approval_reason(self.operation, session_id=True)

    def test_negative_session_denied(self):
        with self.assertRaises(ValueError): approval_reason(self.operation, session_id=-2)

    def test_wrong_action_denied(self):
        with self.assertRaises(ValueError): approval_reason(replace(self.operation, action="pay_now"), session_id=17)

    def test_wrong_risk_denied(self):
        with self.assertRaises(ValueError): approval_reason(replace(self.operation, risk="low"), session_id=17)

    def test_invalid_operation_id_denied(self):
        with self.assertRaises(ValueError): approval_reason(replace(self.operation, operation_id="fake"), session_id=17)

    def test_wrong_target_denied(self):
        with self.assertRaises(ValueError): approval_reason(replace(self.operation, target="zomorodmelal"), session_id=17)

    def test_empty_title_denied(self):
        with self.assertRaises(ValueError): approval_reason(replace(self.operation, parameters={**self.operation.parameters, "title": ""}), session_id=17)

    def test_extra_secret_denied(self):
        with self.assertRaises(ValueError): approval_reason(replace(self.operation, parameters={**self.operation.parameters, "secret": "no"}), session_id=17)

    def test_no_approval_flag_denied(self):
        with self.assertRaises(ValueError): approval_reason(replace(self.operation, approval_required=False), session_id=17)

    def test_valid_zomorod_path(self):
        self.assertTrue(valid_draft_path("/company/services", "zomorodmelal"))

    def test_invalid_zomorod_root(self):
        self.assertFalse(valid_draft_path("/offers", "zomorodmelal"))

    def test_invalid_path_type(self):
        self.assertFalse(valid_draft_path(["/offers"], "mojplaywin"))

    def test_invalid_target_type(self):
        self.assertFalse(valid_draft_path("/offers", ["mojplaywin"]))

    def test_invalid_dot_segment(self):
        self.assertFalse(valid_draft_path("/offers/./other", "mojplaywin"))

    def test_real_owner_flags(self):
        self.assertTrue(is_authorized_chat_operator(SimpleNamespace(is_authenticated=True, is_active=True, is_superuser=True)))

    def test_integer_auth_flag_denied(self):
        self.assertFalse(is_authorized_chat_operator(SimpleNamespace(is_authenticated=1, is_active=True, is_superuser=True)))

    def test_integer_owner_flag_denied(self):
        self.assertFalse(is_authorized_chat_operator(SimpleNamespace(is_authenticated=True, is_active=True, is_superuser=1)))

    def test_missing_owner_flags_denied(self):
        self.assertFalse(is_authorized_chat_operator(SimpleNamespace(is_authenticated=True)))

    def test_owner_none_denied(self):
        self.assertFalse(is_authorized_chat_operator(None))


if __name__ == "__main__":
    unittest.main()
