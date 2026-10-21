#!/usr/bin/env python3
"""Measured Q068 ZIP package integrity evidence only: never expert certification.

Built/unchanged factory archives are checked against actual manifest hashes,
safe ZIP members, CRCs and bounded expansion. An immutable private evidence
file is produced only for a real passing archive; no broad quality claims.
"""
import hashlib,json,os
from pathlib import Path,PurePosixPath
import re,zipfile
HEX=re.compile(r"^[a-f0-9]{64}$")
MAX_MEMBERS=2500
MAX_TOTAL_UNCOMPRESSED=150*1024*1024
MAX_MEMBER_UNCOMPRESSED=40*1024*1024
MAX_ARCHIVE=65*1024*1024
def sha(blob):
    return hashlib.sha256(blob).hexdigest()
def measured_zip_evidence(folder,recipe,archive,manifest):
    folder=Path(folder);archive=Path(archive)
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,65}",str(recipe)):
        return None
    if archive.is_symlink() or not archive.is_file() or not archive.stat().st_size or archive.stat().st_size>MAX_ARCHIVE:
        return None
    wanted=manifest.get("artifact_sha256") if isinstance(manifest,dict) else None
    if not isinstance(wanted,str) or not HEX.fullmatch(wanted):
        return None
    # The actual build is the only source of valid evidence.
    if sha(archive.read_bytes())!=wanted:return None
    try:
        count=0;total=0;members=[]
        with zipfile.ZipFile(archive) as bundle:
            info=bundle.infolist()
            if not 1<=len(info)<=MAX_MEMBERS:return None
            seen=set()
            for item in info:
                name=item.filename
                path=PurePosixPath(name)
                if (name.startswith("/") or "\\" in name or ".." in path.parts
                    or not name.startswith(recipe+"/") or name in seen
                    or item.is_dir() or ((item.external_attr>>16)&0o170000)==0o120000
                    or item.file_size>MAX_MEMBER_UNCOMPRESSED):
                    return None
                seen.add(name);total+=item.file_size
                if total>MAX_TOTAL_UNCOMPRESSED:return None
                # Actually decompresses and checks CRC; bounded before reading.
                payload=bundle.read(item)
                if len(payload)!=item.file_size:return None
                members.append([name,sha(payload),len(payload)])
                count+=1
    except (zipfile.BadZipFile,OSError,RuntimeError,ValueError,EOFError,NotImplementedError):
        return None
    report={
      "schema":"saeit.factory.measured-zip-integrity-q068.v1",
      "criterion":"Q068",
      "scope":"cryptographic_identity_zip_safety_crc_member_integrity_only",
      "recipe":recipe,
      "artifact_sha256":wanted,
      "archive_bytes":archive.stat().st_size,
      "actual_members_tested":count,
      "actual_uncompressed_bytes_tested":total,
      "members_sha256":members,
      "all_crc_and_path_safety_tests_passed":True,
      "excludes":"scientific_veracity_game_originality_human_review_global_quality",
      "professional_quality_1000_approved":False,
    }
    blob=(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
    out=folder/".quality-measurements"
    if out.is_symlink():raise ValueError("QUALITY_EVIDENCE_SYMLINK_REFUSED")
    out.mkdir(mode=0o700,exist_ok=True)
    dest=out/("q068-"+wanted+".json")
    if dest.is_symlink():raise ValueError("QUALITY_EVIDENCE_SYMLINK_REFUSED")
    if dest.exists():
        if dest.read_bytes()!=blob:raise ValueError("QUALITY_EVIDENCE_HASH_CONFLICT")
    else:
        with dest.open("xb") as fh:
            fh.write(blob);fh.flush();os.fsync(fh.fileno())
        dest.chmod(0o600)
    return {"path":dest.relative_to(folder).as_posix(),"sha256":sha(blob)}
