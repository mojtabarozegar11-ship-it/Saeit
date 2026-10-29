#!/usr/bin/env python3
"""Full private web login/CSRF/approval regression on temporary synthetic data."""
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parent.parent
php = shutil.which("php")
assert php, "php missing"
with tempfile.TemporaryDirectory(prefix="zm-flow-web-qa-") as temporary:
    base = pathlib.Path(temporary)
    private = base / ".private/zomorod-business"
    web = base / "public_html/business"
    sessions = base / "sessions"
    private.mkdir(parents=True, mode=0o700)
    web.mkdir(parents=True)
    sessions.mkdir(mode=0o700)
    source = root / "content/zomorod-business"
    for filename in ("app.php", "insights.php", "command_center.php",
                     "command_quality.php", "command_planner.php",
                     "workflow_desk.php", "payroll_control.php", "payroll_ui.php",
                     "treasury_control.php", "treasury_ui.php"):
        shutil.copy2(source / filename, private / filename)
    shutil.copy2(source / "index.php", web / "index.php")
    sid = "zmflowoldtestsession"
    code = (
        "session_id(getenv('SID'));"
        "$_SERVER['REQUEST_METHOD']=getenv('REQ_METHOD');"
        "$_GET=json_decode(getenv('QUERY_JSON'),true);"
        "$_POST=json_decode(getenv('POST_JSON'),true);"
        "require getenv('INDEX');"
    )

    def req(method="GET", page="", post=None):
        nonlocal_sid = None
        env = os.environ.copy()
        env.update({
            "SID": sid,
            "REQ_METHOD": method,
            "QUERY_JSON": json.dumps({"page": page} if page else {}),
            "POST_JSON": json.dumps(post or {}),
            "INDEX": str(web / "index.php"),
        })
        answer = subprocess.run(
            [php, "-d", "session.save_path=" + str(sessions), "-r", code],
            env=env, capture_output=True, text=True, timeout=20)
        assert answer.returncode == 0, answer.stderr[-250:]
        return answer.stdout

    def csrf(text):
        found = re.search(r'name="csrf" value="([0-9a-f]{64})"', text)
        assert found, "csrf missing"
        return found.group(1)

    login = req()
    assert "ورود مدیر و حسابدار" in login
    assert "کارتابل یکپارچه" not in req("GET", "workflow_desk")
    receipt = (private / "owner-first-login.txt").read_text()
    username = re.search(r"^Username: (.+)$", receipt, re.M).group(1)
    password = re.search(r"^Initial password: (.+)$", receipt, re.M).group(1)
    assert not password in login
    first_csrf = csrf(login)
    req("POST", "", {"csrf": first_csrf, "username": username, "password": password})
    # PHP session ID is rotated on login; avoid reliance on old SID by using
    # reading the session files in a strictly synthetic isolated workspace.
    ids = [x.name.removeprefix("sess_") for x in sessions.iterdir() if x.name.startswith("sess_")]
    assert ids
    session_candidates = []
    for candidate in ids:
        content = (sessions / ("sess_" + candidate)).read_bytes()
        if b"uid" in content and b"admin" in content:
            session_candidates.append(candidate)
    assert len(session_candidates) == 1
    sid = session_candidates[0]
    page = req("GET", "workflow_desk")
    assert "کارتابل یکپارچه" in page
    tok = csrf(page)
    request_key = "a" * 32
    response = req("POST", "workflow_desk", {
        "csrf": tok, "action": "flow_create",
        "request_key": request_key,
        "category": "procurement",
        "title": "<script>Synthetic</script>",
        "details": "Synthetic safe procurement request",
        "amount": "125.00",
        "currency": "IRR",
        "risk": "normal",
    })
    assert "درخواست انجام نشد" not in response
    flow_db = sqlite3.connect(str(private / "company-workflow.sqlite3"))
    row = flow_db.execute("SELECT id,state,risk FROM requests").fetchone()
    assert row == (1, "draft", "high_impact"), row
    # No duplicate when an identical key is retried.
    response = req("POST", "workflow_desk", {
        "csrf": tok, "action": "flow_create", "request_key": request_key,
        "category": "procurement", "title": "<script>Synthetic</script>",
        "details": "Synthetic safe procurement request",
        "amount": "125.00", "currency": "IRR", "risk": "normal"
    })
    assert "درخواست انجام نشد" not in response
    assert flow_db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 1
    req("POST", "workflow_desk", {
        "csrf": tok, "action": "flow_transition",
        "request_id": "1", "decision": "submit", "note": "Synthetic handoff"})
    same_person = req("POST", "workflow_desk", {
        "csrf": tok, "action": "flow_transition",
        "request_id": "1", "decision": "approve", "note": "Must reject"})
    assert "درخواست انجام نشد" in same_person
    assert flow_db.execute("SELECT state FROM requests WHERE id=1").fetchone()[0] == "submitted"
    assert "&lt;script&gt;Synthetic" in req("GET", "workflow_desk")
    # Provision a second synthetically logged-in administrator via existing UI.
    other_password = "SyntheticSecondAdminPassword2026!"
    req("POST", "users", {
        "csrf": tok, "action": "user", "username": "synthetic_reviewer",
        "password": other_password, "role": "admin"
    })
    first_admin_sid = sid
    sid = "zmflowreviewersession"
    second_login = req()
    second_csrf = csrf(second_login)
    req("POST", "", {"csrf": second_csrf,
                       "username": "synthetic_reviewer",
                       "password": other_password})
    ids = [x.name.removeprefix("sess_") for x in sessions.iterdir() if x.name.startswith("sess_")]
    reviewers = []
    for candidate in ids:
        if b"uid" in (sessions / ("sess_" + candidate)).read_bytes():
            if b'i:2;' in (sessions / ("sess_" + candidate)).read_bytes():
                reviewers.append(candidate)
    assert len(reviewers) == 1
    sid = reviewers[0]
    tok2 = csrf(req("GET", "workflow_desk"))
    approved = req("POST", "workflow_desk", {
        "csrf": tok2, "action": "flow_transition",
        "request_id": "1", "decision": "approve", "note": "Synthetic second-person review"})
    assert "درخواست انجام نشد" not in approved
    assert flow_db.execute("SELECT state,reviewed_by FROM requests WHERE id=1").fetchone() == ("approved", 2)
    assert flow_db.execute("SELECT COUNT(*) FROM request_events").fetchone()[0] == 3
    # Real authenticated route, CSRF and independent payroll approval.
    payroll_screen = req("GET", "payroll")
    assert "محاسبهٔ پیشنهادی حقوق" in payroll_screen
    bad_csrf = req("POST", "payroll", {"action": "payroll_create",
        "request_key": "c"*32, "period": "2026-10", "employee_0": "EMP001", "base_0": "125.50"})
    assert "درخواست انجام نشد" in bad_csrf
    tok_payroll = csrf(payroll_screen)
    payload = {"csrf": tok_payroll, "action": "payroll_create",
        "request_key": "c"*32, "period": "2026-10", "currency": "IRR",
        "employee_0": "EMP001", "base_0": "125.50",
        "addition_0": "15.25", "deduction_0": "10.00"}
    response = req("POST", "payroll", payload)
    assert "درخواست انجام نشد" not in response
    payroll_db = sqlite3.connect(str(private / "payroll-control.sqlite3"))
    assert payroll_db.execute("SELECT gross_total,net_total FROM payroll_periods").fetchone() == (14075,13075)
    req("POST", "payroll", payload)
    assert payroll_db.execute("SELECT COUNT(*) FROM payroll_periods").fetchone()[0] == 1
    req("POST", "payroll", {"csrf": tok_payroll, "action": "payroll_decision",
        "period_id": "1", "decision": "submit", "reason": "Synthetic submitted"})
    denied_self = req("POST", "payroll", {"csrf": tok_payroll,
        "action": "payroll_decision", "period_id": "1",
        "decision": "approve", "reason": "Cannot self approve"})
    assert "درخواست انجام نشد" in denied_self
    sid = first_admin_sid
    tok_owner = csrf(req("GET", "payroll"))
    accepted = req("POST", "payroll", {"csrf": tok_owner, "action": "payroll_decision",
        "period_id": "1", "decision": "approve", "reason": "Independent owner review"})
    assert "درخواست انجام نشد" not in accepted
    assert payroll_db.execute("SELECT state,reviewed_by FROM payroll_periods").fetchone() == ("approved",1)
    assert payroll_db.execute("SELECT COUNT(*) FROM payroll_events").fetchone()[0] == 3
    # Test new private treasury screen through actual PHP sessions and CSRF.
    treasury_screen = req("GET", "treasury")
    assert "خزانه‌داری — درخواست‌های داخلی" in treasury_screen
    treasury_csrf = csrf(treasury_screen)
    tresp = req("POST", "treasury", {"action": "treasury_create",
        "request_key": "d"*32, "reference": "SYN-REF",
        "purpose": "Forged CSRF must be rejected", "direction": "payable",
        "amount": "12.34", "currency": "IRR"})
    assert "درخواست انجام نشد" in tresp
    proposal = {"csrf": treasury_csrf, "action": "treasury_create",
        "request_key": "d"*32, "reference": "<script>synthetic</script>",
        "purpose": "Synthetic supplier review only", "direction": "payable",
        "amount": "12.34", "currency": "IRR"}
    result = req("POST", "treasury", proposal)
    assert "درخواست انجام نشد" not in result
    treasury_db = sqlite3.connect(str(private / "treasury-control.sqlite3"))
    assert treasury_db.execute("SELECT status,amount_minor FROM treasury_requests").fetchone() == ("draft",1234)
    req("POST", "treasury", proposal)
    assert treasury_db.execute("SELECT COUNT(*) FROM treasury_requests").fetchone()[0] == 1
    assert "&lt;script&gt;synthetic" in req("GET", "treasury")
    req("POST", "treasury", {"csrf": treasury_csrf, "action": "treasury_decision",
        "treasury_id": "1", "decision": "submit", "reason": "Review queue"})
    self_approval = req("POST", "treasury", {"csrf": treasury_csrf,
        "action": "treasury_decision", "treasury_id": "1",
        "decision": "approve", "reason": "Not allowed"})
    assert "درخواست انجام نشد" in self_approval
    sid = reviewers[0]
    other_csrf = csrf(req("GET", "treasury"))
    ok = req("POST", "treasury", {"csrf": other_csrf,
        "action": "treasury_decision", "treasury_id": "1",
        "decision": "approve", "reason": "Independent synthetic approval"})
    assert "درخواست انجام نشد" not in ok
    assert treasury_db.execute("SELECT status,reviewed_by FROM treasury_requests").fetchone() == ("approved",2)
    assert treasury_db.execute("SELECT COUNT(*) FROM treasury_events").fetchone()[0] == 3
    assert treasury_db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    ledger = sqlite3.connect(f"file:{private/'management.sqlite3'}?mode=ro", uri=True)
    assert ledger.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0] == 0
    assert ledger.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 0
    assert ledger.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert flow_db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    print("WORKFLOW_AUTHENTICATED_WEB_QA=PASS")
    print("CSRF_ROLE_CONTROLS=PASS SENSITIVE_TWO_PERSON_APPROVAL=PASS")
    print("IDEMPOTENCY_AUDIT=PASS XSS_ESCAPING=PASS")
    print("ACCOUNTING_ENTRIES=ZERO SYNTHETIC_DATA_ONLY=YES")
    print("PAYROLL_AUTHENTICATED_CSRF_TWO_PERSON_WEB_QA=PASS")
    print("TREASURY_AUTHENTICATED_CSRF_TWO_PERSON_WEB_QA=PASS")
