"""Strict allowlisted receipt validation for the V3 observer. No host access."""
from collections import Counter
from deploy.mojtaba_task_reconciliation_readonly import (
    FACTORY_ACTIONS, REASON_RULES, STATUS, TERMINAL, valid_code,
)

STATES = (STATUS - TERMINAL) | {"unknown_nonterminal"}
FIELDS = {"project_id", "product_id", "factory_run_id"}
LINKS = {"field_absent", "null", "present"}
RUN_LINKS = {"run_missing", "run_product_mismatch", "run_active_product_match", "run_not_active"}
TAGS = {label for label, _ in REASON_RULES} | {"unstructured_reason", "unrecorded_reason", "other_reason"}

def require(condition):
    if not condition:
        raise ValueError("invalid_reconciliation_receipt")

def count(n):
    return type(n) is int and 0 <= n <= 100000

def tags(value):
    return isinstance(value, list) and len(value) > 0 and all(isinstance(x,str) and x in TAGS for x in value) and len(set(value)) == len(value)

def groups(rows, keys, domains):
    require(isinstance(rows, list))
    result = Counter()
    for row in rows:
        require(isinstance(row,dict) and set(row) == set(keys) | {"total"})
        require(count(row["total"]) and row["total"] > 0)
        for k, domain in zip(keys,domains):
            require(domain(row[k]))
        key = tuple(tuple(row[k]) if isinstance(row[k], list) else row[k] for k in keys)
        require(key not in result)
        result[key] = row["total"]
    return result

def validate_reconciliation(r, agents, pending):
    require(isinstance(r,dict) and set(r) == {
        "pending", "groups", "blocked_reason_indicators_nonexclusive", "links",
        "exhausted_groups", "exhausted_cases_snapshot_local", "run_links",
        "same_action_product_run_candidate_groups", "same_action_product_run_candidate_tasks",
        "duplicates_proven", "execution_authorized", "cause_proven_by_keyword"})
    require(count(r["pending"]) and r["pending"] == pending)
    require(all(r[k] is False for k in ("duplicates_proven","execution_authorized","cause_proven_by_keyword")))
    expected = Counter()
    expected_exhausted = Counter()
    for agent in agents:
        for g in agent["pending_groups"]:
            key = g["action"],g["status"]
            expected[key] += g["total"]
            if g["attempt_limit_reached"]:
                expected_exhausted[key] += g["attempt_limit_reached"]
    status = lambda s: isinstance(s,str) and s in STATES
    member = lambda domain: lambda v: isinstance(v,str) and v in domain
    actual = groups(r["groups"],("action","status"),(valid_code,status))
    require(actual == expected and sum(actual.values()) == pending)
    reason = groups(r["blocked_reason_indicators_nonexclusive"],("action","reason_tag"),(valid_code,member(TAGS)))
    for (action,tag),n in reason.items():
        require(n <= actual[action,"blocked"])
    for (action,state),n in actual.items():
        if state == "blocked":
            require(sum(v for (a,_),v in reason.items() if a==action) >= n)
    links = groups(r["links"],("action","status","field","state"),(valid_code,status,member(FIELDS),member(LINKS)))
    link_totals = Counter()
    for (action,state,field,kind),n in links.items():
        link_totals[action,state,field] += n
    require(link_totals == Counter({(a,s,f):n for (a,s),n in actual.items() for f in FIELDS}))
    exhausted = groups(r["exhausted_groups"],("action","status","reason_tags"),(valid_code,status,tags))
    exhausted_totals = Counter()
    for (action,state,reason_tags),n in exhausted.items():
        exhausted_totals[action,state] += n
    require(exhausted_totals == expected_exhausted)
    cases = r["exhausted_cases_snapshot_local"]
    require(isinstance(cases,list) and len(cases) <= 1000 and len(cases)==sum(exhausted.values()))
    case_groups = Counter()
    case_links = Counter()
    case_run_links = Counter()
    for index,c in enumerate(cases,1):
        require(isinstance(c,dict) and set(c)=={"case","action","status","attempts","maximum","reason_tags","links","run_link_state"})
        require(type(c["case"]) is int and c["case"]==index and valid_code(c["action"]) and status(c["status"]) and tags(c["reason_tags"]))
        require(count(c["attempts"]) and count(c["maximum"]) and c["attempts"]>=c["maximum"])
        require(isinstance(c["links"],dict) and set(c["links"])==FIELDS and all(member(LINKS)(v) for v in c["links"].values()))
        require(member(RUN_LINKS | {"not_evaluated"})(c["run_link_state"]))
        for field, state in c["links"].items():
            case_links[c["action"], c["status"], field, state] += 1
        linked = c["action"] in FACTORY_ACTIONS and all(
            c["links"][field] == "present" for field in ("product_id", "factory_run_id"))
        if c["run_link_state"] != "not_evaluated":
            require(linked)
            case_run_links[c["action"],c["run_link_state"]] += 1
        case_groups[c["action"],c["status"],tuple(c["reason_tags"])] += 1
    require(case_groups == exhausted)
    require(all(n <= links[key] for key,n in case_links.items()))
    run = r["run_links"]
    require(isinstance(run,dict) and run.get("state") in {"observed","field_absent_or_no_linked_tasks","run_schema_incomplete"})
    if run["state"] == "observed":
        require(set(run)=={"state","groups"})
        rows=groups(run["groups"],("action","link_state"),(member(FACTORY_ACTIONS),member(RUN_LINKS)))
        require(all(n <= rows[key] for key,n in case_run_links.items()))
        for c in cases:
            if c["action"] in FACTORY_ACTIONS and all(c["links"][f]=="present" for f in ("product_id","factory_run_id")):
                require(c["run_link_state"] != "not_evaluated")
        for action in FACTORY_ACTIONS:
            linked_upper = sum(min(links[action,state,"product_id","present"],
                                   links[action,state,"factory_run_id","present"])
                               for a,state in actual if a==action)
            require(sum(n for (a,_),n in rows.items() if a==action)<=linked_upper)
    else:
        require(set(run)=={"state"} and not case_run_links)
    candidate_groups=r["same_action_product_run_candidate_groups"]
    candidate_tasks=r["same_action_product_run_candidate_tasks"]
    require(count(candidate_groups) and count(candidate_tasks) and 2*candidate_groups<=candidate_tasks<=pending and bool(candidate_groups)==bool(candidate_tasks))
    return r
