"""Evidence-gated briefs for each tenant. No claims or publication without review."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
TERMS = {"personal":("business","management","economics","leadership","research"),"company":("agriculture","farming","research","food","sustainability"),"vancouver_personal":("travel","food","style","lifestyle","vancouver")}
def build_briefs(report):
    briefs = {}
    for tenant, terms in TERMS.items():
        matches = [p for p in report.get("ranked",[]) if any(t in (p.get("title","")+" "+p.get("category","")).lower() for t in terms)]
        briefs[tenant] = {"status":"research_ready_for_editorial_review" if matches else "research_insufficient",
            "sources":[{"url":p["url"],"source_url":p["source_url"]} for p in matches[:5]],
            "can_generate_factual_claims":False, "can_publish":False}
    return briefs
def main():
    output=ROOT/"output"
    report=output/"research_report.json"
    data=json.loads(report.read_text(encoding="utf-8")) if report.exists() else {"ranked":[]}
    (output/"editorial_briefs.json").write_text(json.dumps(build_briefs(data),ensure_ascii=False,indent=2),encoding="utf-8")
    print("Editorial evidence briefs prepared; publishing disabled")
if __name__=="__main__":
    main()
