#!/usr/bin/env python3
"""Read-only 2026-11-04 fragmented SQL backup range/manifest reconciliation.

Read only small .meta files and stat() of matching .sql.gz files on the VPS.
Never open SQL payloads, decrypt, restore, create, delete, move or modify.
No table names, filenames, credentials or row contents in evidence.
A manifest range check does not establish recoverability, gzip CRC, SHA
verification, point-in-time consistency or source currency.
"""
import json,os,pwd,re,stat,sys,time
from pathlib import Path
ROOT=Path("/home/githubops/.db-backups/zomorod2_sites_main-segments-20261104")
DATASETS=("core_agenttask","core_factoryevidence")
PART_RE=re.compile(r"^PARTITION_META table=(core_agenttask|core_factoryevidence) part=(\d+)(?: subpart=(\d+))? rows=(\d+) min=(\d+) max=(\d+) low=(\d+) high=(\d+)$",re.M)
SHA_RE=re.compile(r"^sha256=([0-9a-f]{64})$",re.M)
SIZE_RE=re.compile(r"^compressed_bytes=(\d+)$",re.M)
FILE_RE=re.compile(r"^(core_agenttask|core_factoryevidence)\.(\d+)(?:\.sub(\d+))?\.meta$")
MAX_FILES=128
MAX_META_BYTES=8192

def safe_stat(p):
    try:s=p.lstat()
    except FileNotFoundError:return None
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.geteuid():
        return "UNSAFE_OR_NOT_OWNED"
    return s

def scan():
    rs=ROOT.lstat()
    if not stat.S_ISDIR(rs.st_mode) or rs.st_uid!=os.geteuid() or ROOT.is_symlink():
        raise RuntimeError("BACKUP_ROOT_UNSAFE")
    schema=safe_stat(ROOT/"schema.sql.gz")
    if schema is None:raise RuntimeError("SCHEMA_ARCHIVE_MISSING")
    if isinstance(schema,str):raise RuntimeError("SCHEMA_ARCHIVE_UNSAFE")
    records={}
    n_files=0
    bad_name=0
    other_gz=0
    unmatched=0
    with os.scandir(ROOT) as it:
        names=[]
        for e in it:
            n_files+=1
            if n_files>MAX_FILES:raise RuntimeError("BACKUP_DIRECTORY_OVER_LIMIT")
            names.append(e.name)
    gz_names={n for n in names if n.endswith(".sql.gz") and n!="schema.sql.gz"}
    metadata_names=[n for n in names if n.endswith(".meta")]
    for fname in metadata_names:
        m=FILE_RE.fullmatch(fname)
        if not m:
            bad_name+=1;continue
        table,part,sub=m.groups()
        part=int(part);sub=None if sub is None else int(sub)
        if part not in range(8) or (sub is not None and sub not in range(4)):
            bad_name+=1;continue
        key=(table,part,sub)
        if key in records:raise RuntimeError("DUPLICATE_SEGMENT_META")
        p=ROOT/fname
        st=safe_stat(p)
        if not st or isinstance(st,str) or st.st_size>MAX_META_BYTES:
            raise RuntimeError("SEGMENT_META_UNSAFE")
        source=p.read_text(encoding="utf-8",errors="replace")
        part_rows=PART_RE.findall(source)
        digests=SHA_RE.findall(source);sizes=SIZE_RE.findall(source)
        if len(part_rows)!=1 or len(digests)!=1 or len(sizes)!=1:
            raise RuntimeError("MISSING_OR_MULTIPLE_META_FIELDS")
        row=part_rows[0]
        if row[0]!=table or int(row[1])!=part or (None if row[2]=="" else int(row[2]))!=sub:
            raise RuntimeError("META_FILE_ID_MISMATCH")
        count,minid,maxid,low,high=map(int,row[3:])
        if not (minid<=low<high<=maxid+1) or count<0:
            raise RuntimeError("INVALID_SEGMENT_RANGE")
        gzname=fname[:-5]+".sql.gz"
        gz=safe_stat(ROOT/gzname)
        if not gz or isinstance(gz,str):raise RuntimeError("SEGMENT_PAYLOAD_MISSING_OR_UNSAFE")
        expected=int(sizes[0])
        records[key]={
           "count":count,"min":minid,"max":maxid,
           "low":low,"high":high,
           "payload_size":gz.st_size,"declared_size":expected,
           "declared_checksum":digests[0],
           "size_match":gz.st_size==expected,
        }
    unpaired=sorted(gz_names-{keyname[:-5]+".sql.gz" for keyname in metadata_names})
    if len(unpaired)>MAX_FILES:raise RuntimeError("TOO_MANY_UNPAIRED")
    results={}
    aggregate_selected=0
    all_complete=True
    for alias,table in (("dataset_a",DATASETS[0]),("dataset_b",DATASETS[1])):
        selected=[]
        missing=[]
        alternative_files=0
        for part in range(8):
            original=records.get((table,part,None))
            subs=[records.get((table,part,i)) for i in range(4)]
            if original:
                selected.append(original)
                alternative_files+=sum(s is not None for s in subs)
            elif all(subs):
                selected.extend(subs)
            else:
                missing.append(part)
        spans=sorted(selected,key=lambda x:(x["low"],x["high"]))
        complete=(len(missing)==0 and bool(spans))
        same_bounds=(len({(r["min"],r["max"]) for r in spans})==1) if spans else False
        contiguous=bool(spans) and all(a["high"]==b["low"] for a,b in zip(spans,spans[1:]))
        outer=bool(spans) and spans[0]["low"]==spans[0]["min"] and spans[-1]["high"]==spans[-1]["max"]+1
        sizes_match=all(x["size_match"] for x in spans)
        range_complete=complete and same_bounds and contiguous and outer and sizes_match
        all_complete&=range_complete
        selected_bytes=sum(x["payload_size"] for x in spans)
        aggregate_selected+=selected_bytes
        results[alias]={
           "metadata_segment_count":sum(k[0]==table for k in records),
           "selected_segments":len(spans),
           "missing_base_parts_count":len(missing),
           "alternate_subsegments_not_selected":alternative_files,
           "same_source_min_max_claimed":same_bounds,
           "ranges_contiguous":contiguous,
           "range_covers_claimed_min_max":outer,
           "payload_sizes_match_declared":sizes_match,
           "declared_rows_selected":sum(x["count"] for x in spans),
           "claimed_min_id":spans[0]["min"] if same_bounds else None,
           "claimed_max_id":spans[0]["max"] if same_bounds else None,
           "selected_compressed_bytes":selected_bytes,
           "manifest_range_admissible":range_complete,
           "note":"Metadata claims only; actual checksums, CRC and restore not verified",
        }
    return {
      "schema_file_present":True,"schema_compressed_bytes":schema.st_size,
      "total_directory_entries":n_files,
      "total_meta_files":len(metadata_names),
      "recognized_meta_files":len(records),
      "invalid_or_unrecognized_meta_names":bad_name,
      "sql_gz_file_count":len(gz_names)+1,
      "sql_gz_without_matching_meta":len(unpaired),
      "datasets":results,
      "total_selected_compressed_bytes":aggregate_selected+schema.st_size,
      "all_declared_ranges_complete":all_complete,
      "content_sha256_verified":False,
      "gzip_crc_verified":False,
      "independent_restore_tested":False,
      "historical_backup_currency_proven":False,
      "private_names_disclosed":False,
    }

def main():
    if pwd.getpwuid(os.geteuid()).pw_name!="githubops":
        raise RuntimeError("WRONG_VPS_USER")
    t0=time.monotonic()
    result=scan()
    print("MOJ_FACTORY_VPS_SQL_SEGMENT_RANGE="+json.dumps({
      "schema":"moj.factory.sql-segment-range.readonly.v1",
      "range_inventory":result,
      "files_created":0,"files_deleted":0,"read_only":True,
      "safe_to_delete_original_data":False,
      "elapsed_seconds":round(time.monotonic()-t0,3)
    },sort_keys=True),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("MOJ_FACTORY_VPS_SQL_SEGMENT_RANGE_FAILED="+type(exc).__name__+
              ":"+str(exc)[:70],file=sys.stderr,flush=True)
        sys.exit(1)
