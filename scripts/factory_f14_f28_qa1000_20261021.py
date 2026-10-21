#!/usr/bin/env python3
"""Fail-closed 1,024-case F28 financial oracle + 1,024-case F14 game stress gate.
The verdict is TECHNICAL ONLY. Independent human/release/legal gates stay closed.
"""
import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess

CASES = 1024
INVALID = 256
SCHEMA = "saeit.factory.f14-f28-strict-qa.v1"
SOURCE = {"F14": "fab699b275f04ce69912c56e7d0a881ef9ee2d8d",
          "F28": "458052d5663102f0cc896047e1cad171bb80ef24"}
FILES = {
    "F14/index.html": ("F14", "product_recipes/rootline_bloom_defense/index.html"),
    "F14/game.css": ("F14", "product_recipes/rootline_bloom_defense/game.css"),
    "F14/engine.js": ("F14", "product_recipes/rootline_bloom_defense/engine.js"),
    "F14/game.js": ("F14", "product_recipes/rootline_bloom_defense/game.js"),
    "F14/COMMERCIAL_PILOT.md": ("F14", "product_recipes/rootline_bloom_defense/COMMERCIAL_PILOT.md"),
    "F28/greenhouse_margin_lab_pilot.html": ("F28", "product_recipes/greenhouse_crop_margin/greenhouse_margin_lab_pilot.html"),
    "F28/COMMERCIAL_PILOT.md": ("F28", "product_recipes/greenhouse_crop_margin/COMMERCIAL_PILOT.md"),
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def verify_pinned_source(roots):
    for family, commit in SOURCE.items():
        path = roots[family]
        assert path.is_dir() and not path.is_symlink(), family
        seen = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"],
                                       text=True, timeout=10).strip()
        assert seen == commit, "Unexpected unreviewed source revision for " + family

def samples():
    r = random.Random(202610210104)
    out = []
    for i in range(CASES):
        a = r.randint(1, 1000000) / 100
        y = r.randint(0, 6500) / 100
        price = r.randint(0, 150000) / 100
        variable = r.randint(0, 50000) / 100
        fixed = r.randint(0, 40000000) / 100
        reject = r.randint(0, 10000) / 100
        if i % 127 == 0:
            reject = 100
        if i % 137 == 0:
            y = 0
        if i % 139 == 0:
            variable = 0
            fixed = 0
        if i % 149 == 0:
            a = 0.000001
        out.append({"area": a, "yield": y, "price": price,
                    "variable": variable, "fixed": fixed,
                    "reject": reject, "currency": ["USD", "EUR", "CAD", "IRR"][i % 4]})
    return out

def fail_inputs(good):
    cases = []
    for i in range(INVALID):
        bad = dict(good[i])
        k = i % 11
        if k == 0:
            bad["area"] = 0
        elif k == 1:
            bad["area"] = -100
        elif k == 2:
            bad["yield"] = -1
        elif k == 3:
            bad["price"] = "-Infinity"
        elif k == 4:
            bad["reject"] = 100.01
        elif k == 5:
            bad["reject"] = -0.01
        elif k == 6:
            bad["fixed"] = "NaN"
        elif k == 7:
            bad["variable"] = ""
        elif k == 8:
            bad["currency"] = "<script>alert(1)</script>"
        elif k == 9:
            bad["currency"] = "A" * 50
        elif k == 10:
            bad["area"] = "1e999"
        cases.append(bad)
    return cases

def golden(data):
    v = {k: Decimal(str(value)) for k, value in data.items() if k != "currency"}
    gross = v["area"] * v["yield"]
    saleable = gross * (Decimal(1) - v["reject"] / 100)
    revenue = saleable * v["price"]
    total = v["area"] * v["variable"] + v["fixed"]
    margin = revenue - total
    return {"gross": gross, "saleable": saleable, "revenue": revenue,
            "total": total, "margin": margin, "marginPerArea": margin/v["area"],
            "breakEven": (total/saleable if saleable != 0 else None)}

def check_numeric(good, got):
    assert len(got) == len(good), "Missing financial test cases"
    fields = ("gross", "saleable", "revenue", "total", "margin", "marginPerArea", "breakEven")
    for i, (example, result) in enumerate(zip(good, got)):
        assert result["currency"] == example["currency"], ("currency", i)
        expected = golden(example)
        for key in fields:
            wanted = expected[key]
            seen = result[key]
            if wanted is None:
                assert seen is None, ("zero-yield break-even", i)
                continue
            assert isinstance(seen, (float, int)) and not isinstance(seen, bool), (key, i)
            actual = Decimal(str(seen))
            delta = abs(actual - wanted)
            limit = max(Decimal("0.01"), abs(wanted) * Decimal("0.0000000001"))
            assert delta <= limit, ("financial-oracle-divergence", i, key, str(delta))
        assert result["saleable"] <= result["gross"] + 0.001
        assert result["total"] >= 0
        assert abs((result["revenue"]-result["total"])-result["margin"]) <= max(
            0.01, abs(result["margin"])*1e-10)

def check_offline(roots):
    for name, (fam, rel) in FILES.items():
        path = roots[fam] / rel
        assert path.is_file() and not path.is_symlink(), name
        value = path.read_bytes()
        assert 100 <= len(value) <= 500_000, name
        if name.endswith((".html", ".js", ".css")):
            text = value.decode("utf-8").lower()
            for forbidden in ("https://", "http://", "fetch(", "xmlhttprequest",
                              "importscripts(", "<iframe", "websocket("):
                assert forbidden not in text, ("external-network or embed", name, forbidden)
            if name.endswith(".html"):
                assert "payment" in text or "purchase" in text, name
    game_html = (roots["F14"]/FILES["F14/index.html"][1]).read_text()
    assert game_html.index('src="engine.js"') < game_html.index('src="game.js"')
    assert game_html.count("data-kind=") == 3

def financial_node(roots, good, bad):
    html = (roots["F28"]/FILES["F28/greenhouse_margin_lab_pilot.html"][1]).read_text()
    match = re.search(r"const calculate=(function calculate\(v\)\{.*?\});\s*const keys=", html, re.S)
    assert match, "F28 browser calculator not independently extractable"
    js = ('const calculate=' + match.group(1) + ';\n'
          'let raw="";process.stdin.setEncoding("utf8");'
          'process.stdin.on("data",x=>raw+=x);'
          'process.stdin.on("end",()=>{const d=JSON.parse(raw);'
          'const results=d.good.map(calculate);'
          'let rejected=0;for(const v of d.bad){let fails=false;'
          'try{calculate(v)}catch(_){fails=true}if(fails)rejected++;}'
          'process.stdout.write(JSON.stringify({results,rejected}));});\n')
    p = subprocess.run(["node", "-e", js], input=json.dumps({"good": good, "bad": bad}),
                       capture_output=True, text=True, timeout=50)
    assert p.returncode == 0, p.stderr[-2000:]
    data = json.loads(p.stdout)
    check_numeric(good, data["results"])
    assert data["rejected"] == INVALID, ("F28 invalid cases accepted", data["rejected"])
    return data["rejected"]

def game_node(roots):
    game_script = Path(__file__).with_name("factory_f14_qa1024_game_20261021.js")
    assert game_script.is_file(), "Game adversarial test missing"
    engine = roots["F14"] / FILES["F14/engine.js"][1]
    p = subprocess.run(["node", str(game_script), str(engine), str(CASES)],
                       capture_output=True, text=True, timeout=90)
    assert p.returncode == 0, p.stderr[-3000:]
    result = json.loads(p.stdout)
    assert result["cases"] == CASES
    assert result["failures"] == 0
    assert result["deterministic_replay_verified"] == CASES
    return result

def execute(roots, output):
    verify_pinned_source(roots)
    check_offline(roots)
    good = samples()
    bad = fail_inputs(good)
    invalid_rejected = financial_node(roots, good, bad)
    game = game_node(roots)
    sha = {}
    for name, (family, relative) in FILES.items():
        sha[name] = digest((roots[family] / relative).read_bytes())
    report = {
        "schema": SCHEMA,
        "source_commits": SOURCE,
        "source_file_sha256": sha,
        "financial_oracle_scenarios": CASES,
        "financial_malicious_and_invalid_rejected": invalid_rejected,
        "game_simulations": game["cases"],
        "game_deterministic_replay_verified": game["deterministic_replay_verified"],
        "game_assertion_failures": game["failures"],
        "all_technical_checks_passed": True,
        "specialist_review_passed": False,
        "rights_cleared": False,
        "commercially_approved": False,
        "payment_enabled": False,
        "publicly_published": False,
        "owner_publication_approval": False,
        "release_eligible": False,
        "status": "technical_qa_pass_only",
    }
    out = Path(output)
    assert not out.exists() and not out.is_symlink()
    out.write_text(json.dumps(report, sort_keys=True, indent=2)+"\n")
    print("F28_INDEPENDENT_DECIMAL_ORACLE_SCENARIOS="+str(CASES))
    print("F28_INVALID_INPUT_REJECTED="+str(invalid_rejected))
    print("F14_STATEFUL_ADVERSARIAL_GAME_CASES="+str(game["cases"]))
    print("F14_DETERMINISTIC_REPLAY_VERIFIED="+str(game["deterministic_replay_verified"]))
    print("F14_F28_STRICT_QA=PASS")
    print("F14_F28_COMMERCIAL_APPROVAL=0")
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--f14", required=True)
    parser.add_argument("--f28", required=True)
    parser.add_argument("--report", required=True)
    a = parser.parse_args()
    execute({"F14": Path(a.f14), "F28": Path(a.f28)}, a.report)

if __name__ == "__main__":
    main()
