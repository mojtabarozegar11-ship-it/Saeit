#!/usr/bin/env python3
"""Bounded QA-to-native-rebuild bridge. No authorizations, sales or false QA closeout.

Consumes REAL VPS 1000-point private workorders. Where a factory-owned source
has changed, or an archived ZIP is mechanically broken, rebuilds a fresh private
candidate with the existing tested manufacturer. Never edits original warehouse.
Nonmechanical quality findings remain open for verifiable work by specialists.
"""
import argparse
from html import escape as html_escape
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile
def active_product_allowlist(path):
    """Read line 41's single active product or the legacy five-slot set."""
    state_path = Path(path)
    if state_path.is_symlink() or not state_path.is_file() or state_path.stat().st_size > 2000000:
        raise ValueError("ACTIVE_PRODUCT_SLOTS_REQUIRED")
    state = json.loads(state_path.read_text(encoding="utf8"))
    if not isinstance(state, dict):
        raise ValueError("ACTIVE_PRODUCT_SLOTS_SCHEMA_INVALID")
    active = state.get("active")
    capacity = state.get("capacity")
    current = type(capacity) is int and capacity == 1 and state.get("line_id") == 41
    legacy = type(capacity) is int and capacity == 5
    if (state.get("schema") != "saeit.factory.product-slots.v1"
            or not (current or legacy) or not isinstance(active, list)
            or len(active) != capacity):
        raise ValueError("ACTIVE_PRODUCT_SLOT_CAPACITY_MISMATCH")
    recipes = [item.get("recipe") if isinstance(item, dict) else None for item in active]
    if (len(set(recipes)) != capacity or any(not isinstance(recipe, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{1,65}", recipe) for recipe in recipes)):
        raise ValueError("ACTIVE_PRODUCT_SLOT_ENTRIES_INVALID")
    return set(recipes)


RECIPE=re.compile(r"^[a-z][a-z0-9_]{1,65}$")
HEX=re.compile(r"^[0-9a-f]{64}$")
MECHANICAL=("P0_BUILD_", "P0_ARTIFACT_", "P0_TECHNICAL_")
SCHEMA="saeit.factory.qa-native-rebuild-bridge.v1"

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def load_maker(path):
    if path.is_symlink() or not path.is_file():raise ValueError("PINNED_MAKER_NOT_PRESENT")
    spec=importlib.util.spec_from_file_location("saeit_qa_rebuild_pinned_maker",str(path))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def checked_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2_000_000:
        raise ValueError("UNSAFE_SOURCE_EVIDENCE")
    doc=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(doc,dict):raise ValueError("INVALID_EVIDENCE_DOCUMENT")
    return doc

def atomic_receipt(path,doc):
    blob=(json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
    digest=sha(blob)
    dest=path/("repair-"+digest[:24]+".json")
    if dest.is_symlink():raise ValueError("REPAIR_RECEIPT_SYMLINK")
    if dest.exists():
        if dest.read_bytes()!=blob:raise ValueError("REPAIR_RECEIPT_CONFLICT")
    else:
        path.mkdir(parents=True,mode=0o700,exist_ok=True)
        with dest.open("xb") as f:
            f.write(blob);f.flush();os.fsync(f.fileno())
        os.chmod(dest,0o600)
    return digest

def private_state(path, data):
    """Atomic, private operational state; never a quality approval."""
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("UNSAFE_REBUILD_STATE_PATH")
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".qa-rebuild-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            json.dump(data, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def rotated_orders(orders, cursor):
    if cursor.is_symlink():
        raise ValueError("UNSAFE_REBUILD_CURSOR")
    if not cursor.exists():
        return orders
    saved = checked_json(cursor)
    last = saved.get("last_attempted_recipe")
    if saved.get("schema") != "saeit.factory.qa-rebuild-cursor.v1" or not isinstance(last, str) or not RECIPE.fullmatch(last):
        raise ValueError("INVALID_REBUILD_CURSOR")
    return [row for row in orders if row[0] > last] + [row for row in orders if row[0] <= last]


def failure_state(folder, basis):
    path = folder / ("failures-" + basis[:24] + ".json")
    if path.is_symlink():
        raise ValueError("UNSAFE_REBUILD_FAILURE_LEDGER")
    if not path.exists():
        return path, {"schema": "saeit.factory.qa-rebuild-failure.v1",
                      "basis_sha256": basis, "attempts": 0}
    saved = checked_json(path)
    if (saved.get("schema") != "saeit.factory.qa-rebuild-failure.v1"
            or saved.get("basis_sha256") != basis
            or type(saved.get("attempts")) is not int or saved["attempts"] < 0):
        raise ValueError("INVALID_REBUILD_FAILURE_LEDGER")
    return path, saved


def recover_source_from_archive(root,recipe,order,maker,recovered_root):
    """Recover source only from the original artifact bound to its QA receipt."""
    product=root/"digital-products"/recipe
    manifest=product/"manufacturing_manifest.json"
    archive=product/(recipe+"-internal-qa.zip")
    if not product.exists():return False,None
    if product.is_symlink():return False,"unsafe_archive_path"
    if not archive.is_file():return False,None
    if archive.is_symlink() or (manifest.exists() and manifest.is_symlink()):
        return False,"unsafe_archive_path"
    phase="receipt_preflight"
    try:
        expected_artifact=order.get("artifact_sha256")
        receipt=root/"quality-excellence"/"rework"/recipe/"current.json"
        if (not isinstance(expected_artifact,str) or not HEX.fullmatch(expected_artifact)
                or not receipt.is_file() or receipt.is_symlink()
                or sha(receipt.read_bytes())!=order.get("source_quality_receipt_sha256")
                or checked_json(receipt).get("artifact_sha256")!=expected_artifact):
            return False,"triage_receipt_mismatch"
        phase="manufacturing_manifest"
        try:meta=checked_json(manifest) if manifest.is_file() else {}
        except (ValueError,OSError,UnicodeError):meta={}
        # A bound ZIP is not proof of original *source* unless the exact
        # manufacturing manifest authenticates its complete source file list
        # and the canonical pre-build source hash.
        files=meta.get("files") if meta.get("recipe")==recipe else None
        source_expected=meta.get("source_sha256")
        if (meta.get("qa_status")!="passed"
            or meta.get("commercial_status")!="private_internal_qa_pass_not_published"
            or meta.get("public_listing_enabled") is not False
            or meta.get("owner_publication_approval") is not False):
            return False,"source_manifest_technical_quality_unverified"
        if not isinstance(source_expected,str) or not HEX.fullmatch(source_expected):
            return False,"source_provenance_missing"
        # If the original manifest omitted only the file index, it may be
        # reconstructed from authenticated ZIP members, but ONLY when the
        # complete canonical source digest matches its original SHA256.
        # Malformed *declared* indexes still fail closed.
        if files is not None and (not isinstance(files,list) or not 1<=len(files)<=256
            or any(not isinstance(name,str) or len(name)>240 or "\\" in name
                or not name or name.startswith("/") or
                any(part in ("","..",".") for part in name.split("/"))
                for name in files)
            or len(set(files))!=len(files)):
            return False,"source_file_inventory_not_verifiable"
        phase="original_archive_hash"
        raw=archive.read_bytes()
        if len(raw)>64*1024*1024:return False,"archive_too_large"
        if sha(raw)!=expected_artifact:return False,"archive_hash_mismatch"
        if recovered_root.parent.is_symlink():return False,"unsafe_recovered_root"
        phase="private_staging_root"
        recovered_root.mkdir(parents=True,mode=0o700,exist_ok=True)
        if recovered_root.is_symlink():return False,"unsafe_recovered_root"
        target=recovered_root/recipe
        if target.exists() or target.is_symlink():return False,"recovered_target_conflict"
        phase="private_staging_creation"
        stage=Path(tempfile.mkdtemp(prefix="."+recipe+"-",dir=str(recovered_root)))
        try:
            payload=stage/recipe
            payload.mkdir(mode=0o700)
            phase="zip_structure_validation"
            with zipfile.ZipFile(archive,"r") as zf:
                infos=zf.infolist()
                if not infos or len(infos)>256 or zf.testzip() is not None or sum(i.file_size for i in infos)>64*1024*1024:
                    return False,"archive_members_invalid"
                archive_names=[]
                for info in infos:
                    if info.is_dir():return False,"archive_members_invalid"
                    name=info.filename
                    rel=PurePosixPath(name)
                    if not name or "\\" in name or rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
                        return False,"archive_members_invalid"
                    archive_names.append(rel.as_posix())
                if len(set(archive_names))!=len(archive_names):return False,"archive_members_invalid"
                if all(name.startswith(recipe+"/") for name in archive_names):
                    names=[name[len(recipe)+1:] for name in archive_names]
                elif all("/" not in name for name in archive_names):
                    names=list(archive_names)
                else:
                    top={name.split("/",1)[0] for name in archive_names}
                    if len(top)!=1 or any("/" not in name for name in archive_names):
                        return False,"archive_members_invalid"
                    wrapper=next(iter(top))
                    names=[name[len(wrapper)+1:] for name in archive_names]
                normalized=sorted(files) if files is not None else sorted(names)
                if sorted(names)!=normalized:return False,"archive_members_invalid"
                phase="zip_member_extraction"
                for info,name in zip(infos,names):
                    if stat.S_ISLNK(info.external_attr>>16):return False,"archive_symlink_member"
                    dest=payload/name
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(zf.read(info));os.chmod(dest,0o600)
            # Do not disclose archived names or exception messages: only the
            # fixed stage and exception class are aggregated in private QA.
            # A customer-delivery ZIP that lacks executable original source
            # must remain unbuildable, never silently synthesized.
            phase="native_recipe_inspection"
            try:
                _,checked_files=maker.inspect_recipe(payload)
            except RuntimeError:
                # The manufacturer requires an authentic README and original
                # test_*.py source. Delivery-only archives are not recipes.
                # Inspect verified member names only; never expose them.
                if "README.md" not in normalized:
                    return False,"original_recipe_readme_missing"
                if not any(PurePosixPath(name).name.startswith("test_")
                           and name.endswith(".py") for name in normalized):
                    return False,"original_recipe_tests_missing"
                return False,"original_recipe_contract_rejected"
            phase="canonical_source_digest"
            source_hash=maker.source_digest(payload,checked_files)
            if tuple(checked_files)!=tuple(normalized) or source_hash!=source_expected:
                return False,"source_hash_mismatch"
            phase="verified_source_promotion"
            os.chmod(payload,0o700);os.replace(payload,target)
            return True,None
        finally:
            if stage.exists():shutil.rmtree(stage)
    except zipfile.BadZipFile:return False,"archive_invalid_zip"
    except (OSError,ValueError,RuntimeError,UnicodeError,KeyError) as error:
        # Stable, non-sensitive reason: never print exception text, paths,
        # member names or customer document bytes. No provenance gate relaxed.
        return False,"archive_"+phase+"_"+type(error).__name__.lower()


def classify_unrecoverable_artifact(root,recipe):
    """Inspect only archive metadata and count material types; reveal no filenames."""
    stock=root/"digital-products"/recipe
    meta=stock/"manufacturing_manifest.json"
    archive=stock/(recipe+"-internal-qa.zip")
    facts={}
    if stock.is_symlink() or meta.is_symlink() or archive.is_symlink():
        return {"unsafe_stock_path":1}
    try:
        if not meta.is_file():facts["no_manufacturing_manifest"]=1
        else:
            data=checked_json(meta)
            if not isinstance(data.get("source_sha256"),str) or not HEX.fullmatch(data.get("source_sha256","")):
                facts["source_hash_absent"]=1
            if not isinstance(data.get("files"),list):facts["source_file_manifest_absent"]=1
            if data.get("qa_status")!="passed":facts["prior_qa_not_passed"]=1
            if not isinstance(data.get("family_id"),str):facts["family_identity_unbound"]=1
        if not archive.is_file():facts["archive_not_present"]=1
        elif archive.stat().st_size>65*1024*1024:facts["archive_overlarge"]=1
        else:
            with zipfile.ZipFile(archive) as zf:
                infos=zf.infolist()
                if not 1<=len(infos)<=2500:facts["archive_member_count_invalid"]=1
                else:
                    parts=[PurePosixPath(item.filename) for item in infos]
                    if not all(len(p.parts)>=2 and p.parts[0]==recipe for p in parts):
                        facts["customer_delivery_layout_not_source_recipe"]=1
                    if not any(p.name.startswith("test_") and p.suffix==".py" for p in parts):
                        facts["no_embedded_source_tests"]=1
                    extensions={p.suffix.lower() for p in parts}
                    groups={
                        "code":{".py",".js",".ts",".jsx",".tsx",".php"},
                        "document":{".pdf",".docx",".md",".txt",".epub"},
                        "media":{".png",".jpg",".jpeg",".webp",".mp3",".wav",".mp4"},
                        "web":{".html",".css",".svg"},
                        "structured_data":{".json",".csv",".xlsx",".db",".sqlite"}}
                    for category,values in groups.items():
                        if extensions.intersection(values):facts["contains_"+category]=1
    except (OSError,ValueError,RuntimeError,UnicodeError,zipfile.BadZipFile,KeyError,EOFError):
        facts["unreadable_legacy_archive_format"]=1
    return facts




def repair_document_edition_stock(code,source_parent,package_parent,receipt_parent,
                                  package_dir,receipt_file,prior,maker):
    """Rebuild a verified private edition with an atomic, retained old-stock backup.

    A failed builder never destroys the previously issued package or receipt.
    No original customer ZIP or specialist quality approval is touched.
    """
    pending=receipt_parent/(code+".json.pending")
    if pending.exists() or pending.is_symlink():
        return "private_edition_receipt_conflict"
    if package_dir.is_symlink() or (package_dir.exists() and not package_dir.is_dir()):
        return "unsafe_document_edition_root"
    backup=Path(tempfile.mkdtemp(prefix=".edition-repair-"+code+"-",
                                 dir=str(package_parent)))
    os.chmod(backup,0o700)
    old=backup/"prior-stock"
    moved=False
    try:
        if package_dir.exists():
            os.replace(package_dir,old)
            moved=True
        result=maker.manufacture(code,source_parent,package_parent)
        meta=checked_json(package_dir/"manufacturing_manifest.json")
        package=package_dir/(code+"-internal-qa.zip")
        if (result.get("qa_status")!="passed" or meta.get("qa_status")!="passed"
                or meta.get("source_sha256")!=prior.get("new_source_sha256")
                or not package.is_file() or package.is_symlink()
                or maker.sha256_file(package)!=meta.get("artifact_sha256")):
            raise ValueError("PRIVATE_EDITION_REBUILD_QA_NOT_VERIFIED")
        updated=dict(prior)
        updated["new_artifact_sha256"]=meta["artifact_sha256"]
        with pending.open("x",encoding="utf8") as writer:
            json.dump(updated,writer,sort_keys=True,indent=2)
            writer.write("\n")
            writer.flush()
            os.fsync(writer.fileno())
        os.chmod(pending,0o600)
        os.replace(pending,receipt_file)
        return "private_document_edition_repaired"
    except (OSError,ValueError,RuntimeError,TypeError,KeyError):
        # Preserve the failed new package for private engineering inspection.
        # Restore the prior package by atomic rename on the same filesystem.
        if pending.is_file() and not pending.is_symlink():
            pending.unlink()
        if package_dir.is_dir() and not package_dir.is_symlink():
            os.replace(package_dir,backup/"failed-stock")
        if moved and old.is_dir() and not package_dir.exists() and not package_dir.is_symlink():
            os.replace(old,package_dir)
        return "private_edition_rebuild_failed"
    finally:
        if not moved and backup.is_dir() and not any(backup.iterdir()):
            backup.rmdir()



def reauthor_document_delivery(root,recipe,order,maker):
    """Create a NEW, private offline document-reader source, not fake old source.

    Original customer ZIP bytes must match their independently stored QA return
    receipt. We treat untrusted documents as DATA, never execute archived code.
    A new recipe is tested by the real manufacturer and stays commercially
    blocked pending all original 1000-point specialist/rights checks.
    """
    stock=root/"digital-products"/recipe
    archive=stock/(recipe+"-internal-qa.zip")
    qa=root/"quality-excellence"/"rework"/recipe/"current.json"
    expected=order.get("artifact_sha256")
    if (stock.is_symlink() or archive.is_symlink() or qa.is_symlink()
            or not archive.is_file() or not qa.is_file()
            or not isinstance(expected,str) or not HEX.fullmatch(expected)):
        return "unverifiable_original_archive"
    dest=None
    package_dir=None
    receipt_file=None
    created_source=False
    try:
        if (sha(qa.read_bytes())!=order.get("source_quality_receipt_sha256")
                or checked_json(qa).get("artifact_sha256")!=expected):
            return "original_qa_receipt_not_bound"
        if not 0<archive.stat().st_size<=65*1024*1024:
            return "original_archive_size_invalid"
        h=hashlib.sha256()
        with archive.open("rb") as fh:
            for chunk in iter(lambda:fh.read(65536),b""):
                h.update(chunk)
        if h.hexdigest()!=expected:
            return "original_archive_sha_mismatch"
        code="edition_"+expected[:24]
        source_parent=root/"quality-excellence"/"document-edition-sources"
        package_parent=root/"quality-excellence"/"document-edition-private-stock"
        receipt_parent=root/"quality-excellence"/"document-edition-receipts"
        if any(p.is_symlink() for p in (source_parent,package_parent,receipt_parent)):
            return "unsafe_document_edition_root"
        for p in (source_parent,package_parent,receipt_parent):
            p.mkdir(mode=0o700,parents=True,exist_ok=True)
        dest=source_parent/code
        receipt_file=receipt_parent/(code+".json")
        package_dir=package_parent/code
        if dest.exists() or dest.is_symlink():
            if dest.is_symlink() or not dest.is_dir():
                return "existing_edition_source_path_unsafe"
            if receipt_file.is_symlink() or not receipt_file.is_file():
                return "existing_edition_receipt_missing_or_unsafe"
            try:
                prior=checked_json(receipt_file)
            except (ValueError,OSError,UnicodeError,TypeError):
                return "existing_edition_receipt_invalid"
            if prior.get("source_customer_archive_sha256")!=expected:
                return "existing_edition_receipt_provenance_mismatch"
            if (prior.get("commercial_release_authorized") is not False
                    or prior.get("technical_manufacturer_qa_passed") is not True):
                return "existing_edition_receipt_qa_not_verifiable"
            try:
                _,existing_files=maker.inspect_recipe(dest)
                same_source=(maker.source_digest(dest,existing_files)
                             ==prior.get("new_source_sha256"))
            except (OSError,ValueError,RuntimeError,UnicodeError):
                return "existing_edition_source_invalid"
            if not same_source:
                return "existing_edition_source_hash_mismatch"
            out=package_dir/"manufacturing_manifest.json"
            package=package_dir/(code+"-internal-qa.zip")
            if (not package_dir.is_symlink() and out.is_file() and not out.is_symlink()
                    and package.is_file() and not package.is_symlink()):
                try:
                    meta=checked_json(out)
                    if (meta.get("qa_status")=="passed"
                            and meta.get("source_sha256")==prior.get("new_source_sha256")
                            and meta.get("artifact_sha256")==prior.get("new_artifact_sha256")
                            and maker.sha256_file(package)==prior.get("new_artifact_sha256")):
                        return "already_issued_private_edition"
                except (OSError,ValueError,UnicodeError):
                    pass
            return repair_document_edition_stock(
                code,source_parent,package_parent,receipt_parent,
                package_dir,receipt_file,prior,maker)
        if package_dir.exists() or package_dir.is_symlink():
            return "orphaned_edition_stock_requires_review"
        ALLOWED={".md",".txt",".pdf",".docx",".epub",".csv",".json",
                 ".xlsx",".png",".jpg",".jpeg",".webp",".mp3",".wav",".mp4"}
        TEXT={".md",".txt",".csv",".json"}
        entries=[];total=0;omitted=0
        with zipfile.ZipFile(archive) as zf:
            members=zf.infolist()
            if not 1<=len(members)<=2500:
                return "original_archive_member_count_invalid"
            visited=set()
            for item in members:
                filename=item.filename
                rel=PurePosixPath(filename)
                if (filename.startswith("/") or "\\" in filename or
                    rel.is_absolute() or ".." in rel.parts or not rel.parts or
                    stat.S_ISLNK(item.external_attr>>16) or
                    (item.flag_bits&1) or filename in visited or len(filename)>260):
                    return "unsafe_document_archive_member"
                visited.add(filename)
                # Directory entries are common in authentic delivery ZIPs.
                # They are never materialized and cannot affect safe new paths.
                if item.is_dir():
                    continue
                suffix=rel.suffix.lower()
                if suffix not in ALLOWED:
                    omitted+=1
                    continue
                if item.file_size>16*1024*1024:
                    return "document_asset_over_limit"
                total+=item.file_size
                if total>48*1024*1024:
                    return "document_bundle_over_limit"
                content=zf.read(item)
                if len(content)!=item.file_size:
                    return "document_asset_size_error"
                entries.append((rel.name, suffix, content))
        if not entries or not any(ext in {".txt",".md",".pdf",".docx",".epub"}
                                  for _,ext,_ in entries):
            return "no_supported_document_content"
        # Keep private QA ZIP within the 256-member sender/receiver gate:
        # 200 assets + index, metadata, README and executable QA source.
        # Unpacked input remains limited to 48 MiB independently.
        if len(entries)>200:
            return "document_asset_count_over_limit"
        source_stage=Path(tempfile.mkdtemp(prefix=".document-edition-",dir=str(source_parent)))
        try:
            # Every original path is replaced by a safe generated flat filename.
            assets=source_stage/"assets"
            assets.mkdir(mode=0o700)
            verified=[];nav=[];previews=[]
            # Bound generated inline HTML size; link ALL original supported
            # assets even when previews are omitted for memory/size safety.
            preview_bytes_remaining=1_500_000
            for index,(original,ext,payload) in enumerate(entries,1):
                safe="file_%03d%s"%(index,ext)
                target=assets/safe
                with target.open("xb") as stream:
                    stream.write(payload);stream.flush();os.fsync(stream.fileno())
                os.chmod(target,0o600)
                label="".join(x for x in original if x.isprintable())[:100] or safe
                digest=sha(payload)
                verified.append({"path":"assets/"+safe,"sha256":digest,
                                 "bytes":len(payload),"type":ext,
                                 "display_name":label})
                nav.append('<li><a href="assets/%s" download>%s</a> <small>(%s)</small></li>'%
                           (safe,html_escape(label,quote=True),html_escape(ext)))
                if ext in TEXT and 0<len(payload)<=200000 and len(payload)<=preview_bytes_remaining:
                    content=payload.decode("utf8","replace")
                    preview_bytes_remaining-=len(payload)
                    previews.append('<section aria-label="Text preview"><h2>%s</h2><pre>%s</pre></section>'%
                        (html_escape(label,quote=True),html_escape(content)))
            title=recipe.replace("_"," ").title()
            html='''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>%s | Offline document edition</title>
<style>body{font:16px/1.7 system-ui;margin:0;background:#101922;color:#f5f2e8}
main{max-width:980px;margin:auto;padding:2rem}a{color:#f1ce7f}
nav,section{border:1px solid #927b4b;border-radius:12px;margin:1rem 0;padding:1.25rem}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#1c2933;padding:1rem}
:focus-visible{outline:3px solid #f1ce7f}small{color:#b2b6ba}
</style></head><body><a href="#content">Skip to content</a>
<main id="content"><h1>%s</h1><p>Offline private technical reading edition. Scientific and legal reviews remain pending.</p>
<nav aria-label="Document and asset links"><h2>Available files</h2><ul>%s</ul></nav>
%s
<footer>Local files only. No claims of professional approval or commercial release.</footer>
</main></body></html>'''%(html_escape(title),html_escape(title),
                           "".join(nav),"".join(previews))
            edition={
                "schema":"saeit.factory.private-document-edition.v1",
                "original_recipe":recipe,"original_artifact_sha256":expected,
                "new_recipe":code,"assets":verified,
                "ignored_potentially_executable_or_unsupported_members":omitted,
                "source_restored_from_original":False,
                "input_files_executed":False,
                "new_technical_source_created":True,
                "independent_scientific_or_rights_review_verified":False,
                "commercial_release_authorized":False}
            (source_stage/"index.html").write_text(html,encoding="utf8")
            (source_stage/"metadata.json").write_text(json.dumps(edition,sort_keys=True,
                  indent=2,ensure_ascii=False)+"\n",encoding="utf8")
            (source_stage/"README.md").write_text(
                "# Offline document edition\n\nA genuinely new, generated accessible "
                "offline index of verified private customer-delivery assets; not a "
                "restoration of a missing historical build source. Original input SHA256: "
                +expected+"\n\nThis is a technical candidate only. Rights, real-world "
                "accuracy, professional 1000/1000 review and owner approval remain pending.\n",
                encoding="utf8")
            testcase='''import hashlib,html,json,re,unittest
from pathlib import Path
BASE=Path(__file__).resolve().parent
class EditionTests(unittest.TestCase):
 def test_every_asset_is_present_and_byte_identical(self):
  info=json.loads((BASE/"metadata.json").read_text(encoding="utf8"))
  self.assertFalse(info["commercial_release_authorized"])
  self.assertFalse(info["source_restored_from_original"])
  self.assertGreaterEqual(len(info["assets"]),1)
  for file in info["assets"]:
   path=BASE/file["path"]
   self.assertTrue(path.is_file())
   self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),file["sha256"])
 def test_offline_accessibility_and_escaped_document_labels(self):
  info=json.loads((BASE/"metadata.json").read_text(encoding="utf8"))
  page=(BASE/"index.html").read_text(encoding="utf8")
  self.assertIn('aria-label="Document and asset links"',page)
  self.assertIn("Content-Security-Policy",page)
  self.assertNotIn("<script",page.lower())
  self.assertFalse(re.search(r"""(?:src|href)\s*=\s*["']https?://""",page,re.I))
  for item in info["assets"]:
   self.assertIn('href="'+item["path"]+'"',page)
   self.assertIn(html.escape(item["display_name"],quote=True),page)
'''
            (source_stage/"test_reader.py").write_text(testcase,encoding="utf8")
            for name in ("index.html","metadata.json","README.md","test_reader.py"):
                os.chmod(source_stage/name,0o600)
            if dest.exists() or dest.is_symlink():
                return "document_edition_source_collision"
            os.replace(source_stage,dest)
            created_source=True
        finally:
            if source_stage.exists():
                shutil.rmtree(source_stage)
        # Run actual new-source tests, build a genuinely different private ZIP.
        result=maker.manufacture(code,source_parent,package_parent)
        new_meta=checked_json(package_parent/code/"manufacturing_manifest.json")
        new_archive=package_dir/(code+"-internal-qa.zip")
        if not (result.get("qa_status")=="passed"
                and new_meta.get("qa_status")=="passed"
                and new_meta.get("recipe")==code
                and new_archive.is_file() and not new_archive.is_symlink()
                and maker.sha256_file(new_archive)==new_meta.get("artifact_sha256")
                and new_meta.get("artifact_sha256")!=expected):
            return "new_document_edition_technical_qa_failed"
        proof={
            "schema":"saeit.factory.document-reauthor-receipt.v1",
            "source_customer_archive_sha256":expected,
            "original_recipe":recipe,
            "new_edition_recipe":code,
            "new_source_sha256":new_meta["source_sha256"],
            "new_artifact_sha256":new_meta["artifact_sha256"],
            "technical_manufacturer_qa_passed":True,
            "assets_verified":len(entries),"technical_qa_only":True,
            "old_archive_mutated":False,
            "external_independent_review_verified":False,
            "commercial_release_authorized":False}
        with receipt_file.open("x",encoding="utf8") as writer:
            json.dump(proof,writer,sort_keys=True,indent=2);writer.write("\n")
            writer.flush();os.fsync(writer.fileno())
        os.chmod(receipt_file,0o600)
        return "private_document_edition_built"
    except (OSError,ValueError,UnicodeError,RuntimeError,TypeError,
            zipfile.BadZipFile,KeyError,EOFError,NotImplementedError):
        # Retry transient maker/receipt failures from the same authenticated
        # archive; do not strand unreceipted generated source or partial stock.
        for candidate in ((dest if created_source else None),
                          (package_dir if created_source else None)):
            if candidate is not None and candidate.is_dir() and not candidate.is_symlink():
                shutil.rmtree(candidate)
        return "document_edition_failed_needs_engineering"


def execute(root,source_root,maker_path,*,limit=2,additional_source_roots=(),products_file=None):
    """Rebuild from either verified generated or installed native recipe roots."""
    root=Path(root);source_root=Path(source_root);maker_path=Path(maker_path)
    if not root.is_dir() or root.is_symlink():raise ValueError("PRIVATE_FACTORY_ROOT_INVALID")
    if not source_root.is_dir() or source_root.is_symlink():raise ValueError("PRIVATE_SOURCE_ROOT_INVALID")
    if not isinstance(additional_source_roots,(list,tuple)) or len(additional_source_roots)>2:
        raise ValueError("BOUNDED_SOURCE_ROOTS_REQUIRED")
    # Installed factory sources are stored outside private generated recipes.
    # Discover only the canonical sibling under the same factory-runtime root.
    # Preserve the explicit override for isolated CI fixtures and operators.
    canonical=root.parent.parent/"operations"/"autonomous-product-runtime"/"product_recipes"
    if not additional_source_roots and canonical.is_dir():
        if canonical.is_symlink():
            raise ValueError("CANONICAL_PRODUCT_RECIPES_SYMLINK_UNSAFE")
        additional_source_roots=[canonical]
    roots=[source_root]
    for extra in additional_source_roots:
        candidate=Path(extra)
        if candidate.is_symlink() or not candidate.is_dir():
            raise ValueError("ADDITIONAL_RECIPE_ROOT_UNSAFE_OR_MISSING")
        if candidate.resolve() in (item.resolve() for item in roots):
            raise ValueError("DUPLICATE_SOURCE_ROOT")
        roots.append(candidate)
    recovered_root=root/"quality-excellence"/"recovered-verified-sources"
    if recovered_root.exists() or recovered_root.is_symlink():
        if recovered_root.is_symlink() or not recovered_root.is_dir():
            raise ValueError("RECOVERED_SOURCE_ROOT_UNSAFE")
        if recovered_root.resolve() in (item.resolve() for item in roots):
            raise ValueError("DUPLICATE_SOURCE_ROOT")
        roots.append(recovered_root)
    edition_source=root/"quality-excellence"/"document-edition-sources"
    if edition_source.exists() or edition_source.is_symlink():
        if edition_source.is_symlink() or not edition_source.is_dir():
            raise ValueError("DOCUMENT_EDITION_SOURCE_UNSAFE")
        if edition_source.resolve() in (p.resolve() for p in roots):
            raise ValueError("DOCUMENT_EDITION_DUPLICATE_SOURCE_ROOT")
        roots.append(edition_source)
    if type(limit) is not int or not 1<=limit<=3:raise ValueError("BOUNDED_CAP_REQUIRED")
    maker=load_maker(maker_path)
    workorders=root/"quality-excellence"/"production-workorders"
    if not workorders.is_dir() or workorders.is_symlink():
        raise ValueError("ACTUAL_QA_WORKORDERS_NOT_PRESENT")
    active_products=active_product_allowlist(products_file) if products_file else None
    output=root/"quality-excellence"/"rebuilt-technical-candidates"
    output.mkdir(parents=True,mode=0o700,exist_ok=True)
    if output.is_symlink():raise ValueError("UNSAFE_REBUILD_DESTINATION")
    receipts=root/"quality-excellence"/"native-rebuild-receipts"
    if receipts.is_symlink():raise ValueError("UNSAFE_REPAIR_RECEIPT_ROOT")
    totals={"orders_seen":0,"sources_available":0,"source_changed":0,
            "rebuild_attempted":0,"technical_candidates_verified":0,
            "unchanged_or_human_only":0,"missing_source":0,"failed":0,
            "archive_sources_recovered":0,"archive_recovery_rejected":0,
            "archive_recovery_rejection_reasons":{},
            "document_editions_queued_for_strict_review":0,
            "private_document_editions_built":0,
            "private_document_edition_outcomes":{},
            "legacy_source_gap_causes":{},
            "verified_source_roots":len(roots),
            "source_root_hits":[0 for _ in roots],
            "duplicate_recipe_roots_blocked":0,
            "root_cause_review_pending":0,"failure_escalations_created":0}
    orders=[]
    for folder in sorted(workorders.iterdir()):
        if active_products is not None and folder.name not in active_products:
            continue
        if folder.is_symlink() or not folder.is_dir() or not RECIPE.fullmatch(folder.name):
            continue
        current=folder/"current.json"
        if not current.is_file() or current.is_symlink():continue
        order=checked_json(current)
        if order.get("schema")!="saeit.factory.production-rework-order.v1" or order.get("recipe")!=folder.name:
            continue
        if not isinstance(order.get("source_quality_receipt_sha256"),str) or not HEX.fullmatch(order["source_quality_receipt_sha256"]):
            continue
        if not isinstance(order.get("unresolved_technical_or_domain_defects",[]),list):
            continue
        orders.append((folder.name,order))
    cursor=root/"quality-excellence"/"native-rebuild-cursor.json"
    orders=rotated_orders(orders,cursor)
    for recipe,order in orders:
        totals["orders_seen"]+=1
        locations=[(index,parent,parent/recipe)
                   for index,parent in enumerate(roots)
                   if (parent/recipe).is_dir() and not (parent/recipe).is_symlink()]
        if not locations:
            restored,rejection=recover_source_from_archive(root,recipe,order,maker,recovered_root)
            if rejection:
                totals["archive_recovery_rejected"]+=1
                reasons=totals["archive_recovery_rejection_reasons"]
                reasons[rejection]=reasons.get(rejection,0)+1
            if restored:
                totals["archive_sources_recovered"]+=1
                if recovered_root.resolve() not in (item.resolve() for item in roots):
                    roots.append(recovered_root);totals["source_root_hits"].append(0)
                    totals["verified_source_roots"]=len(roots)
                index=next(i for i,item in enumerate(roots)
                           if item.resolve()==recovered_root.resolve())
                locations=[(index,recovered_root,recovered_root/recipe)]
            else:
                totals["missing_source"]+=1
                if totals["private_document_editions_built"]<6:
                    outcome=reauthor_document_delivery(root,recipe,order,maker)
                    results=totals["private_document_edition_outcomes"]
                    results[outcome]=results.get(outcome,0)+1
                    if outcome=="private_document_edition_built":
                        totals["private_document_editions_built"]+=1
                causes=totals["legacy_source_gap_causes"]
                for reason in classify_unrecoverable_artifact(root,recipe):
                    causes[reason]=causes.get(reason,0)+1
                continue
        # Never make an arbitrary selection if two roots own the same recipe.
        # A genuine source collision needs operator provenance resolution.
        if len(locations)>1:
            totals["duplicate_recipe_roots_blocked"]+=1
            continue
        index,active_root,source=locations[0]
        try:
            _,files=maker.inspect_recipe(source)
            source_hash=maker.source_digest(source,files)
        except (OSError,ValueError,RuntimeError,UnicodeError):
            totals["missing_source"]+=1
            continue
        totals["sources_available"]+=1
        totals["source_root_hits"][index]+=1
        original=root/"digital-products"/recipe/"manufacturing_manifest.json"
        is_edition=source.parent.resolve()==edition_source.resolve()
        if is_edition:
            original=root/"quality-excellence"/"document-edition-private-stock"/recipe/"manufacturing_manifest.json"
        prior=checked_json(original) if original.is_file() and not original.is_symlink() else {}
        changed=prior.get("source_sha256")!=source_hash
        if is_edition:
            totals["document_editions_queued_for_strict_review"]+=1
        mechanical=any(isinstance(code,str) and code.startswith(MECHANICAL)
                       for code in order.get("unresolved_technical_or_domain_defects",[]))
        if not changed and not mechanical:
            totals["unchanged_or_human_only"]+=1
            continue
        if changed:totals["source_changed"]+=1
        receipt_folder=receipts/recipe
        if receipt_folder.is_symlink():raise ValueError("UNSAFE_RECIPE_RECEIPT")
        # Per exact source + QA order. A repeated failed build may be retried on
        # the next authorized run; successful immutable receipts are idempotent.
        basis=sha((recipe+source_hash+order["source_quality_receipt_sha256"]).encode())
        proof=receipt_folder/("source-"+basis[:24]+".json")
        if proof.is_file() and not proof.is_symlink():
            prior_proof=checked_json(proof)
            if prior_proof.get("status")=="technical_candidate_verified":
                continue
        failure_path,failures=failure_state(receipt_folder,basis)
        if failures["attempts"]>=3:
            totals["root_cause_review_pending"]+=1
            continue
        if totals["rebuild_attempted"]>=limit:continue
        totals["rebuild_attempted"]+=1
        private_state(cursor,{"schema":"saeit.factory.qa-rebuild-cursor.v1",
                              "last_attempted_recipe":recipe})
        try:
            result=maker.manufacture(recipe,active_root,output)
            target=output/recipe
            meta=checked_json(target/"manufacturing_manifest.json")
            package=target/(recipe+"-internal-qa.zip")
            if (meta.get("qa_status")!="passed" or meta.get("source_sha256")!=source_hash
                or not package.is_file() or package.is_symlink()
                or maker.sha256_file(package)!=meta.get("artifact_sha256")
                or result.get("qa_status")!="passed"):
                raise ValueError("REBUILD_TECHNICAL_QA_NOT_VERIFIED")
            record={"schema":SCHEMA,"recipe":recipe,"source_sha256":source_hash,
                    "source_root_slot":index,
                    "source_order_sha256":order["source_quality_receipt_sha256"],
                    "artifact_sha256":meta["artifact_sha256"],
                    "source_changed":changed,
                    "status":"technical_candidate_verified",
                    "independent_quality_1000_passed":False,
                    "commercial_release_authorized":False,
                    "original_stock_mutated":False}
            atomic_receipt(receipt_folder,record)
            receipt_folder.mkdir(parents=True,mode=0o700,exist_ok=True)
            if proof.is_symlink():raise ValueError("UNSAFE_SUCCESS_MARKER")
            if proof.is_file():
                if checked_json(proof)!=record:raise ValueError("CONFLICTING_SUCCESS_MARKER")
            else:
                with proof.open("x",encoding="utf8") as f:
                    json.dump(record,f,ensure_ascii=False,sort_keys=True)
                    f.write("\n")
                    f.flush();os.fsync(f.fileno())
                os.chmod(proof,0o600)
            totals["technical_candidates_verified"]+=1
        except (ValueError,OSError,RuntimeError,AssertionError,KeyError,TypeError) as error:
            totals["failed"]+=1
            failures["attempts"]+=1
            failures["last_error_type"]=type(error).__name__
            failures["status"]=("ROOT_CAUSE_REVIEW_REQUIRED" if failures["attempts"]>=3
                                else "RETRY_WITH_SAME_PROVENANCE")
            private_state(failure_path,failures)
            if failures["attempts"]==3:
                totals["failure_escalations_created"]+=1
    totals.update({"schema":SCHEMA,"commercial_release_authorized":False,
                   "professional_quality_1000_verified":False,
                   "all_40_native_executors_proven":False})
    print("FACTORY_REAL_NATIVE_REBUILD="+json.dumps(totals,sort_keys=True))
    return totals

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--private-root",required=True)
    p.add_argument("--source-root",required=True)
    p.add_argument("--additional-source-root",action="append",default=[])
    p.add_argument("--maker",required=True)
    p.add_argument("--limit",type=int,default=2)
    p.add_argument("--products-file",default=None)
    a=p.parse_args()
    execute(a.private_root,a.source_root,a.maker,limit=a.limit,
            additional_source_roots=a.additional_source_root,products_file=a.products_file)

if __name__=="__main__":main()

