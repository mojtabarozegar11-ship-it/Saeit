"""Read-only complete V91 original inventory vs MojPlayWin imported originals.

Never executes original modules or imports Django. Source already independently
preserved on cPanel. Only paths and structural code features are output.
"""
import ast,hashlib,io,json,tarfile
from pathlib import Path
ARCHIVE=Path("/home/zomorod2/.v91_agents_safety_copy/v91-master-and-site-agents-20261018.tar.gz")
PORTED=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018/mpw_v91_port/ORIGIN.json")
ORIGINAL_SHA="4b825f80e06d632d5aac1717f82fac32b731ca89247a45b48f2222bdd86c858c"
assert ARCHIVE.is_file() and not ARCHIVE.is_symlink() and ARCHIVE.stat().st_size<500000
raw=ARCHIVE.read_bytes()
assert hashlib.sha256(raw).hexdigest()==ORIGINAL_SHA
installed=json.loads(PORTED.read_text(encoding="utf8"))
already=set(x["source"] for x in installed["modules"])
found=[];all_paths=[]
with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as tar:
    manifest=json.load(tar.extractfile("V91_AGENT_MANIFEST.json"))
    for rec in manifest["files"]:
        source=rec["path"]
        all_paths.append(source)
        if source in already:continue
        suffix=Path(source).suffix
        data=tar.extractfile(source).read()
        assert hashlib.sha256(data).hexdigest()==rec["sha256"]
        if suffix!=".py":
            found.append({"path":source,"kind":"non_python"})
            continue
        try:
            tree=ast.parse(data.decode("utf8"))
        except (UnicodeError,SyntaxError):
            found.append({"path":source,"kind":"invalid_python"});continue
        imports=sorted(set((n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)))
        calls=set(getattr(n.func,"attr","") for n in ast.walk(tree) if isinstance(n,ast.Call))
        classes=[n.name for n in tree.body if isinstance(n,ast.ClassDef)]
        functions=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
        risk=(("django" in imports) or bool(set(calls)&{"save","create","update","delete","run","execute","publish"}))
        found.append({"path":source,"kind":"Django_or_write_dependent" if risk else "standalone_candidate",
                      "classes":classes[:6],"functions":functions[:7]})
assert len(all_paths)==203
assert len(already)==installed["file_count"]
assert already.issubset(set(all_paths))
from collections import Counter
print(json.dumps({"kind":"V91_203_SOURCE_GAP_INVENTORY_READ_ONLY",
    "source_total":len(all_paths),"previously_imported":len(already),
    "not_imported":len(found),"classification_counts":dict(Counter(x["kind"] for x in found)),
    "unported":found,
    "zomorod_site_modified":False,"mpw_site_modified":False,
    "factory_touched":False,"no_original_python_executed":True},ensure_ascii=False,sort_keys=True))
