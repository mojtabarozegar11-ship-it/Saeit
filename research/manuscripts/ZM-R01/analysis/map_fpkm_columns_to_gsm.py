#!/usr/bin/env python3
"""Map every original GEO FPKM column to GSM via independent GEO metadata labels.
Metadata concordance does not prove sequencing-library biological identity.
Usage: python map_fpkm_columns_to_gsm.py source.xlsx manifest.csv --output mapping.json
"""
import argparse,csv,hashlib,json,re,zipfile
from pathlib import Path
from audit_fpkm_matrix import EXPECTED_SHA,shared_strings,worksheet_rows
p=argparse.ArgumentParser();p.add_argument("xlsx",type=Path);p.add_argument("manifest",type=Path);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
assert hashlib.sha256(a.xlsx.read_bytes()).hexdigest()==EXPECTED_SHA
factor_to_code={(0,0,0):"CTR",(1,0,0):"D",(0,1,0):"eT",(0,0,1):"eC",(1,1,0):"TD",(1,0,1):"CD",(0,1,1):"CT",(1,1,1):"CTD"}
with a.manifest.open(newline="") as fh: rows=list(csv.DictReader(fh))
assert len(rows)==24
lookup={}
for r in rows:
    key=(factor_to_code[(int(r["drought"]),int(r["heat"]),int(r["co2"]))],int(r["biological_replicate"]))
    assert key not in lookup,key
    lookup[key]=r
with zipfile.ZipFile(a.xlsx) as z:
    it=worksheet_rows(z,shared_strings(z))
    header=next(it)
assert len(header)==25 and header[0]=="gene_id"
mapped=[]
for h in header[1:]:
    m=re.fullmatch(r"(CTR|eT|eC|D|CT|CD|TD|CTD)(?:_R)?([123])_FL",h)
    assert m,h
    key=(m.group(1),int(m.group(2)))
    r=lookup[key]
    mapped.append({"xlsx_column":h,"group":key[0],"replicate":key[1],
       "GSM":r["accession"],"GEO_sample_title":r["sample_title"],
       "drought":int(r["drought"]),"heat":int(r["heat"]),"co2":int(r["co2"])})
assert len(mapped)==24 and len({r["GSM"] for r in mapped})==24
assert {r["GSM"] for r in mapped}=={r["accession"] for r in rows}
result={"source_sha256":EXPECTED_SHA,"mapping_basis":"workbook header condition/replicate vs original GEO manifest factor metadata",
"mapped_columns":24,"unique_GSM":24,"status":"metadata-concordant, sequencing identity not independently validated",
"mapping":mapped}
a.output.write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({"mapped_columns":24,"unique_GSM":24,"first":mapped[0],"last":mapped[-1]},indent=2))
