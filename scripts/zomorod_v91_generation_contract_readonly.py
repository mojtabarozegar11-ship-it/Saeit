"""Read only exact V91 content input contract, no execution or DB."""
import ast,json
from pathlib import Path
root=Path("/home/zomorod2/saeit_v91/zomorodmelal/portal")
queries={"generator.py":["valid_sources"],"agent_engine.py":["build_output","clean_text"]}
ans={}
for file,names in queries.items():
    source=(root/file).read_text(encoding="utf8")
    tree=ast.parse(source)
    ans[file]=[]
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names:
            ans[file].append({"function":node.name,"source":(ast.get_source_segment(source,node) or "")[:9700]})
print(json.dumps({"kind":"V91_GENERATOR_SOURCE_CONTRACT","read_only":True,"contracts":ans}))
