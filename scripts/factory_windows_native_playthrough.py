#!/usr/bin/env python3
"""Exercise genuine Windows PE EXE payloads: 48 complete games and CSV edge-cases.

Independent acceptance runner executes *packaged .exe binaries* (not source).
Windows CI environment != independent customer hardware/security review.
"""
import argparse
from collections import deque
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

DIRECTIONS=(("w",-6),("a",-1),("s",6),("d",1))
def winexe(path,args=(),data=None,expected_exit=0,timeout=18):
    proc=subprocess.run([str(path),*map(str,args)],input=data,text=True,
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                        timeout=timeout,check=False)
    if (expected_exit == 0 and proc.returncode != 0 or
            expected_exit != 0 and proc.returncode == 0):
        raise RuntimeError("WINDOWS_PE_BEHAVIOR_WRONG_EXIT stdout="+
                           proc.stdout[-350:]+" stderr="+proc.stderr[-350:])
    return proc.stdout

def route(board):
    walls=set(board["walls"])
    start=int(board["start"])
    goal=int(board["goal"])
    if (not 0 <=start <36 or not 0<=goal<36 or start==goal
            or start in walls or goal in walls
            or any(type(x) is not int or not 0<=x<36 for x in walls)):
        raise RuntimeError("WINDOWS_GAME_BAD_BOARD")
    q=deque([(start,[])])
    visited={start}
    while q:
        position,moves=q.popleft()
        for key,offset in DIRECTIONS:
            new=position+offset
            if not 0<=new<36 or new in walls or new in visited:
                continue
            if key in ("a","d") and new//6!=position//6:
                continue
            if new==goal:
                return moves+[key]
            visited.add(new)
            q.append((new,moves+[key]))
    raise RuntimeError("WINDOWS_GAME_UNSOLVABLE_LEVEL")

def gameplay(exe,levels):
    records=json.loads(Path(levels).read_text("utf8"))
    if len(records)!=48 or len({v.get("id") for v in records})!=48:
        raise RuntimeError("WINDOWS_GAME_NOT_48_LEVELS")
    lengths=[]
    for index,level in enumerate(records):
        moves=route(level)
        output=winexe(exe,("--level",str(index+1)),
                      "\n".join(moves)+"\n",timeout=15)
        if "Solved!" not in output:
            raise RuntimeError("WINDOWS_GAME_PACKAGED_EXE_DID_NOT_SOLVE_"+str(index+1))
        lengths.append(len(moves))
    winexe(exe,("--level","0"),expected_exit=2)
    winexe(exe,("--level","49"),expected_exit=2)
    return {"game_families":48,"playthroughs_from_actual_exe":48,
            "level_paths_verified":48,
            "shortest_solutions_min":min(lengths),
            "shortest_solutions_max":max(lengths),
            "invalid_level_indices_rejected":True}

def accounting(exe):
    cases=[
        ("quantity,unit_price\n3,1.25\n7,2.50\n",10,Decimal("21.25")),
        ("quantity,unit_price\n0,0\n",0,Decimal("0")),
        ("quantity,unit_price\n1000000,1000000000\n",1000000,Decimal("1000000000000000")),
        ("quantity,unit_price\n1,0.00001\n2,10.2345\n",3,Decimal("20.46901")),
        ("quantity,unit_price\n",0,Decimal("0")),
        ("quantity,unit_price\n9,1.1\n3,2.1\n",12,Decimal("16.2"))
    ]
    bad=[
        "quantity,unit_price\n-1,4\n",
        "quantity,unit_price\n1,-0.2\n",
        "quantity,unit_price\n1000001,0.2\n",
        "quantity,unit_price\n2,1000000001\n",
        "quantity,unit_price\n1,NaN\n",
        "quantity,unit_price\nX,1\n",
        "quantity,unit_price\n2,\n",
        "quantity,unit_price\n1,Infinity\n",
        "quantity,unit_price\n1\n"
    ]
    with tempfile.TemporaryDirectory() as folder:
        csv=Path(folder)/"check.csv"
        for source,count,total in cases:
            csv.write_text(source,encoding="utf8")
            raw=winexe(exe,("--csv",str(csv)))
            try:
                parsed=json.loads(raw.strip())
            except json.JSONDecodeError as exc:
                raise RuntimeError("WINDOWS_INVENTORY_OUTPUT_NOT_JSON") from exc
            if parsed.get("total_quantity")!=count or Decimal(parsed["inventory_value"])!=total:
                raise RuntimeError("WINDOWS_INVENTORY_ACCOUNTING_ERROR")
        for source in bad:
            csv.write_text(source,encoding="utf8")
            winexe(exe,("--csv",str(csv)),expected_exit=1)
    return {"real_packaged_csv_invoices_tested":len(cases),
            "invalid_inventory_rows_rejected":len(bad),
            "exact_decimal_math_verified":True}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--f13",required=True)
    p.add_argument("--f17",required=True)
    p.add_argument("--levels",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    exes={"F13":Path(args.f13),"F17":Path(args.f17)}
    checks={}
    for family,exe in exes.items():
        if not exe.is_file() or exe.is_symlink() or exe.stat().st_size < 30_000:
            raise RuntimeError("WINDOWS_REAL_NATIVE_BINARY_REQUIRED:"+family)
        with exe.open("rb") as stream:
            dos=stream.read(256)
        if dos[:2]!=b"MZ" or len(dos)<64:
            raise RuntimeError("WINDOWS_BINARY_INVALID_DOS_HEADER")
        position=int.from_bytes(dos[60:64],"little")
        with exe.open("rb") as stream:
            stream.seek(position)
            if stream.read(4)!=b"PE\x00\x00":
                raise RuntimeError("WINDOWS_BINARY_INVALID_PE_SIGNATURE")
        checks[family]={"sha256":hashlib.sha256(exe.read_bytes()).hexdigest()}
    checks["F13"].update(gameplay(exes["F13"],args.levels))
    checks["F17"].update(accounting(exes["F17"]))
    receipt={
        "schema":"saeit.factory.windows-native-interactive-acceptance.v1",
        "real_windows_runner_execute":True,"families":checks,
        "physical_customer_hardware_reviewed":False,
        "independent_security_expert_approved":False,
        "quality_1000_certified":False,"public_release":False
    }
    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print("FACTORY_WINDOWS_EXECUTABLE_PLAYTHROUGHS=48")
    print("FACTORY_WINDOWS_ACTUAL_CSV_ACCEPTANCE=15")
    print("FACTORY_WINDOWS_INDEPENDENT_REVIEW_REQUIRED=true")

if __name__=="__main__":
    main()
