"""Read-only selected original V91 pure policy and product agent algorithms."""
import ast,io,hashlib,json,tarfile
from pathlib import Path
p=Path("/home/zomorod2/.v91_agents_safety_copy/v91-master-and-site-agents-20261018.tar.gz")
raw=p.read_bytes()
assert hashlib.sha256(raw).hexdigest()=="4b825f80e06d632d5aac1717f82fac32b731ca89247a45b48f2222bdd86c858c"
names=["portal/commercial_quality.py","portal/autopilot_rules.py","portal/editorial_review_v26.py",
       "portal/venture_engine.py","portal/workbook_generator.py",
       "portal/site_cycle_budget.py","portal/commercial_leads.py","portal/title_match.py"]
res=[]
with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as t:
 for name in names:
  f="zomorodmelal/"+name
  s=t.extractfile(f).read().decode("utf8")
  tree=ast.parse(s)
  im=[ast.unparse(n) if hasattr(ast,"unparse") else type(n).__name__ for n in tree.body
      if isinstance(n,(ast.Import,ast.ImportFrom))]
  res.append({"module":name,"bytes":len(s),"imports":im[:12],"source":s[:5400]})
print(json.dumps({"result":"V91_SELECTED_POLICIES","files":res},ensure_ascii=False))
