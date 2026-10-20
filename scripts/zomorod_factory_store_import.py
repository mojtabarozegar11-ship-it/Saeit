#!/usr/bin/env python3
"""Site-only Zomorod private store draft import of VPS warehouse receipts.
No prices, purchases, payment activation, or public product activation.
Every imported item is a verified received factory package, not a sale-ready good.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import sys
import zipfile

SLUG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_ZIP = 25 * 1024 * 1024
SCHEMA = "saeit.zomorod.factory-store-drafts.v1"


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def validate_received(root, receipt):
    if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size>40000:
        raise ValueError("INVALID_RECEIPT")
    doc=json.loads(receipt.read_text(encoding="utf-8"))
    recipe,d=doc.get("recipe"),doc.get("sha256")
    if (not isinstance(recipe,str) or not SLUG.fullmatch(recipe) or
        not isinstance(d,str) or not SHA.fullmatch(d) or
        doc.get("status")!="received_private" or
        receipt.parent.name!=recipe or receipt.name!=d+".json"):
        raise ValueError("RECEIPT_IDENTITY_FAILED")
    pack=root/"packages"/recipe/(d+".zip")
    manifest=root/"packages"/recipe/(d+".json")
    for p in (pack,manifest):
        if p.is_symlink() or not p.is_file():raise ValueError("PACKAGE_MISSING")
    if pack.stat().st_size<100 or pack.stat().st_size>MAX_ZIP or manifest.stat().st_size>100000:
        raise ValueError("PACKAGE_SIZE_INVALID")
    m=json.loads(manifest.read_text(encoding="utf-8"))
    if (m.get("recipe")!=recipe or m.get("artifact_sha256")!=d or
        m.get("qa_status")!="passed" or
        m.get("commercial_status")!="private_internal_qa_pass_not_published" or
        m.get("public_listing_enabled") is not False or
        m.get("owner_publication_approval") is not False or
        m.get("price") is not None):
        raise ValueError("PACKAGE_QA_OR_COMMERCIAL_POLICY")
    if digest(pack)!=d:raise ValueError("ARCHIVE_SHA_MISMATCH")
    with zipfile.ZipFile(pack) as archive:
        infos=archive.infolist()
        if not infos or len(infos)>80 or sum(i.file_size for i in infos)>100*1024*1024:
            raise ValueError("ARCHIVE_LIMIT")
        if archive.testzip() is not None:raise ValueError("ARCHIVE_CHECK_FAILED")
        for i in infos:
            path=i.filename
            if (not path.startswith(recipe+"/") or ".." in path.split("/") or
                path.startswith("/") or "\\" in path or
                (i.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("ARCHIVE_MEMBER_UNSAFE")
    title=str(m.get("name") or recipe).strip()
    if not 3<=len(title)<=160:raise ValueError("PRODUCT_TITLE_INVALID")
    return {"product_id":recipe,"sha256":d,"title":title,
            "family_id":str(m.get("family_id") or "")[:12],
            "source":"vps_factory_verified_private_delivery",
            "status":"awaiting_commercial_and_owner_approval"}


def customer_candidates(root,limit=20):
    """Only private deliverables WITH authenticated prior technical store draft."""
    parent=root/"customer-receipts"
    if parent.is_symlink():raise ValueError("CUSTOMER_RECEIPT_DIRECTORY_SYMLINK")
    if not parent.is_dir():return []
    verifier_path=root/"bin/store_receiver.py"
    if verifier_path.is_symlink() or not verifier_path.is_file():
        raise ValueError("CUSTOMER_RECEIVER_MISSING")
    module=importlib.util.spec_from_file_location("zm_private_store_receiver",verifier_path)
    verifier=importlib.util.module_from_spec(module);module.loader.exec_module(verifier)
    rows=[]
    for product in sorted(parent.iterdir()):
        if product.is_symlink() or not product.is_dir() or not SLUG.fullmatch(product.name):
            raise ValueError("CUSTOMER_RECEIPT_PRODUCT_UNSAFE")
        for row in product.iterdir():
            if row.is_symlink() or not row.is_file() or not row.name.endswith(".json") or not SHA.fullmatch(row.stem):
                raise ValueError("CUSTOMER_RECEIPT_VERSION_UNSAFE")
            if not verifier.consumer_status(root,product.name,row.stem):
                raise ValueError("CUSTOMER_RECEIPT_NOT_SHA_VERIFIED")
            meta=verifier.verify_consumer(root,product.name,row.stem,
                root/"customer-packages"/product.name/row.stem/"customer-package.zip",
                root/"customer-packages"/product.name/row.stem/"candidate_manifest.json")
            rows.append({"product_id":product.name,"source_sha":row.stem,
                        "original_sha":meta["factory_internal_zip_sha256"],
                        "package_sha":meta["package_sha256"],
                        "title":str(meta.get("name",""))[:160]})
            if len(rows)>10000:raise ValueError("CUSTOMER_CANDIDATES_LIMIT")
    return sorted(rows,key=lambda x:(x["product_id"],x["source_sha"]))[:limit]


def import_catalog(root,dbfile,limit=6):
    root=Path(root);dbfile=Path(dbfile)
    if root.is_symlink() or not root.is_dir() or dbfile.is_symlink() or not dbfile.is_file():
        raise ValueError("STORE_OR_INBOX_UNAVAILABLE")
    if not 1<=limit<=20:raise ValueError("IMPORT_LIMIT")
    receipts=root/"receipts"
    if receipts.is_symlink():raise ValueError("RECEIPT_DIR_SYMLINK")
    files=[]
    # Initialize the private store draft catalog even when the factory has
    # no QC-passed goods to deliver yet. Never invent product entries.
    for folder in sorted(receipts.iterdir()) if receipts.is_dir() else []:
        if folder.is_symlink() or not folder.is_dir() or not SLUG.fullmatch(folder.name):
            raise ValueError("RECEIPT_FOLDER_UNSAFE")
        for p in sorted(folder.iterdir()):
            if p.is_symlink() or not p.is_file() or not p.name.endswith(".json"):
                raise ValueError("RECEIPT_ENTRY_UNEXPECTED")
            files.append(p)
    # New arrivals must not be starved by repeatedly scanning the first older receipts.
    if len(files)>10000:raise ValueError('RECEIPT_INDEX_TOO_LARGE')
    files.sort(key=lambda p:(p.stat().st_mtime,p.name),reverse=True)
    connection=sqlite3.connect(str(dbfile),timeout=12,isolation_level=None)
    try:
        tables={x[0] for x in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"products","payment_state"}.issubset(tables):
            raise ValueError("NOT_NATIVE_ZOMOROD_STORE_DATABASE")
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("""CREATE TABLE IF NOT EXISTS factory_drafts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE, title TEXT NOT NULL, family_id TEXT NOT NULL,
            source TEXT NOT NULL, state TEXT NOT NULL,
            public_enabled INTEGER NOT NULL DEFAULT 0 CHECK(public_enabled=0),
            paid_price_irr INTEGER, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK(paid_price_irr IS NULL))""")
        connection.execute("""CREATE TABLE IF NOT EXISTS factory_consumer_candidates(
            product_id TEXT NOT NULL, source_sha256 TEXT NOT NULL,
            original_artifact_sha256 TEXT NOT NULL, package_sha256 TEXT NOT NULL,
            title TEXT NOT NULL, state TEXT NOT NULL,
            public_enabled INTEGER NOT NULL DEFAULT 0 CHECK(public_enabled=0),
            paid_price_irr INTEGER CHECK(paid_price_irr IS NULL),
            PRIMARY KEY(product_id,source_sha256))""")
        imported=existing=scanned=0
        invalid_archive_blocked=0
        for p in files:
            try:
                info=validate_received(root,p)
            except ValueError as error:
                # Preserve an oversized/overpopulated source archive for
                # independent rework, but never allow it to block unrelated
                # already verified private drafts. All OTHER errors fail closed.
                if str(error)!="ARCHIVE_LIMIT":
                    raise
                invalid_archive_blocked+=1
                continue
            if connection.execute('SELECT 1 FROM factory_drafts WHERE sha256=?',(info['sha256'],)).fetchone():
                existing+=1
                continue
            if scanned>=limit:break
            scanned+=1
            connection.execute("BEGIN IMMEDIATE")
            try:
                cur=connection.execute("""INSERT OR IGNORE INTO factory_drafts
                    (product_id,sha256,title,family_id,source,state,public_enabled,paid_price_irr)
                    VALUES(?,?,?,?,?,?,0,NULL)""",
                    (info["product_id"],info["sha256"],info["title"],info["family_id"],
                     info["source"],info["status"]))
                imported+=int(cur.rowcount==1);existing+=int(cur.rowcount!=1)
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK");raise
        customers=customer_candidates(root,limit=limit)
        consumer_new=consumer_existing=0
        for row in customers:
            # A genuine original ZIP must have a matching private draft.
            if not connection.execute("SELECT 1 FROM factory_drafts WHERE product_id=? AND sha256=?",
                    (row["product_id"],row["original_sha"])).fetchone():
                continue
            found=connection.execute("""SELECT package_sha256 FROM factory_consumer_candidates
                    WHERE product_id=? AND source_sha256=?""",
                    (row["product_id"],row["source_sha"])).fetchone()
            if found:
                if found[0]!=row["package_sha"]:raise ValueError("CONSUMER_VERSION_SHA_COLLISION")
                consumer_existing+=1
                continue
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute("""INSERT INTO factory_consumer_candidates
                    (product_id,source_sha256,original_artifact_sha256,package_sha256,title,state,
                     public_enabled,paid_price_irr)
                    VALUES(?,?,?,?,?,'awaiting_independent_commercial_review',0,NULL)""",
                    (row["product_id"],row["source_sha"],row["original_sha"],
                     row["package_sha"],row["title"]))
                consumer_new+=1
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK");raise
        return {"imported":imported,"already":existing,"scanned":scanned,
                "customer_bundles_new":consumer_new,
                "customer_bundles_already":consumer_existing,
                "invalid_archive_blocked":invalid_archive_blocked,
                "public_customer_bundles":0}
    finally:connection.close()



def import_verified_private_shards(batch_dir, dbfile, verifier_file):
    """Bridge independent private receiver proof into existing native store DB.

    This is NOT a sale-ready product, a human review, or an owner signature.
    No mutations to native products, payments, factory_drafts or public listings.
    """
    batch_dir=Path(batch_dir);dbfile=Path(dbfile);verifier_file=Path(verifier_file)
    if (batch_dir.is_symlink() or not batch_dir.is_dir()
            or dbfile.is_symlink() or not dbfile.is_file()
            or verifier_file.is_symlink() or not verifier_file.is_file()):
        raise ValueError("PRIVATE_SHARD_STORE_INPUT_UNSAFE")
    if not SHA.fullmatch(batch_dir.name):
        raise ValueError("PRIVATE_SHARD_BATCH_ID_INVALID")
    receipt=batch_dir/"verification.json"
    if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size>100000:
        raise ValueError("PRIVATE_SHARD_BATCH_RECEIPT_INVALID")
    spec=importlib.util.spec_from_file_location("verified_private_shard_reader",str(verifier_file))
    if spec is None or spec.loader is None:
        raise ValueError("PRIVATE_SHARD_VERIFIER_UNAVAILABLE")
    verifier=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    proven=verifier.verify(batch_dir)
    recorded=json.loads(receipt.read_text(encoding="utf8"))
    if recorded!=dict(proven, encrypted_transport_archive_sha256=batch_dir.name):
        raise ValueError("PRIVATE_SHARD_BATCH_RECEIPT_MISMATCH")
    if (proven.get("products_verified")!=5 or proven.get("shards_verified")!=10
            or proven.get("files_reconstructed")!=485
            or proven.get("publicly_published") is not False
            or proven.get("store_product_created") is not False
            or proven.get("customer_payment_created") is not False
            or proven.get("owner_publication_approval") is not False):
        raise ValueError("PRIVATE_SHARD_RELEASE_OR_RECONSTRUCTION_UNSAFE")
    products=proven["products"]
    if len({p["recipe"] for p in products})!=5:
        raise ValueError("PRIVATE_SHARD_PRODUCT_DUPLICATE")
    record_sha=hashlib.sha256(receipt.read_bytes()).hexdigest()
    with sqlite3.connect(str(dbfile),timeout=20) as db:
        db.execute("PRAGMA busy_timeout=10000")
        existing_tables={name for (name,) in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"products","payment_state"}.issubset(existing_tables):
            raise ValueError("NOT_NATIVE_ZOMOROD_STORE_DATABASE")
        db.execute("""CREATE TABLE IF NOT EXISTS factory_private_shard_candidates(
            recipe TEXT NOT NULL, original_zip_sha256 TEXT NOT NULL,
            private_batch_sha256 TEXT NOT NULL, receiver_receipt_sha256 TEXT NOT NULL,
            shards INTEGER NOT NULL, verified_files INTEGER NOT NULL,
            technical_transport_verified INTEGER NOT NULL CHECK(technical_transport_verified=1),
            release_state TEXT NOT NULL DEFAULT 'awaiting_evidence_and_human_review'
               CHECK(release_state='awaiting_evidence_and_human_review'),
            scientific_review TEXT NOT NULL DEFAULT 'not_verified'
               CHECK(scientific_review='not_verified'),
            rights_and_license_review TEXT NOT NULL DEFAULT 'not_verified'
               CHECK(rights_and_license_review='not_verified'),
            independent_specialist_review TEXT NOT NULL DEFAULT 'not_verified'
               CHECK(independent_specialist_review='not_verified'),
            owner_approval TEXT NOT NULL DEFAULT 'not_granted'
               CHECK(owner_approval='not_granted'),
            public_enabled INTEGER NOT NULL DEFAULT 0 CHECK(public_enabled=0),
            paid_price_irr INTEGER DEFAULT NULL CHECK(paid_price_irr IS NULL),
            PRIMARY KEY(recipe,original_zip_sha256))""")
        db.execute("""CREATE TABLE IF NOT EXISTS factory_shard_evidence_queue(
            recipe TEXT NOT NULL, original_zip_sha256 TEXT NOT NULL,
            needs_scientific_or_functional_evidence INTEGER NOT NULL CHECK(needs_scientific_or_functional_evidence=1),
            needs_rights_and_assets_chain INTEGER NOT NULL CHECK(needs_rights_and_assets_chain=1),
            needs_independent_domain_review INTEGER NOT NULL CHECK(needs_independent_domain_review=1),
            needs_owner_release_signature INTEGER NOT NULL CHECK(needs_owner_release_signature=1),
            evidence_collection_state TEXT NOT NULL DEFAULT 'missing_verifiable_dossiers'
              CHECK(evidence_collection_state='missing_verifiable_dossiers'),
            independent_technical_package_check INTEGER NOT NULL CHECK(independent_technical_package_check=1),
            PRIMARY KEY(recipe,original_zip_sha256))""")
        new=already=0
        for p in products:
            recipe=p["recipe"]; original=p["original_sha256"]
            if not SLUG.fullmatch(recipe) or not SHA.fullmatch(original):
                raise ValueError("PRIVATE_SHARD_PRODUCT_ID_INVALID")
            if type(p.get("shards")) is not int or type(p.get("reconstructed_files")) is not int:
                raise ValueError("PRIVATE_SHARD_PRODUCT_COUNT_INVALID")
            previous=db.execute(
                "SELECT private_batch_sha256,receiver_receipt_sha256,shards,verified_files,"
                "release_state,public_enabled,paid_price_irr FROM factory_private_shard_candidates "
                "WHERE recipe=? AND original_zip_sha256=?",(recipe,original)).fetchone()
            if previous:
                # A prior identical artifact may have been transferred in another
                # tar batch; SHA-bound receipt remains immutable for first intake.
                if (previous[2:] != (p["shards"],p["reconstructed_files"],
                        "awaiting_evidence_and_human_review",0,None)):
                    raise ValueError("PRIVATE_SHARD_CANDIDATE_COLLISION")
                already+=1
            else:
                db.execute("""INSERT INTO factory_private_shard_candidates
                   (recipe,original_zip_sha256,private_batch_sha256,receiver_receipt_sha256,
                    shards,verified_files,technical_transport_verified)
                    VALUES(?,?,?,?,?,?,1)""",
                    (recipe,original,batch_dir.name,record_sha,p["shards"],p["reconstructed_files"]))
                new+=1
            db.execute("""INSERT OR IGNORE INTO factory_shard_evidence_queue
                (recipe,original_zip_sha256,needs_scientific_or_functional_evidence,
                 needs_rights_and_assets_chain,needs_independent_domain_review,
                 needs_owner_release_signature,independent_technical_package_check)
                 VALUES(?,?,1,1,1,1,1)""",(recipe,original))
        for row in db.execute("""SELECT recipe,original_zip_sha256 FROM factory_private_shard_candidates
                WHERE public_enabled<>0 OR paid_price_irr IS NOT NULL
                   OR scientific_review<>'not_verified' OR rights_and_license_review<>'not_verified'
                   OR independent_specialist_review<>'not_verified' OR owner_approval<>'not_granted'"""):
            raise ValueError("PRIVATE_SHARD_RELEASE_GATE_CHANGED")
        return {"new_private_store_candidates":new,"previously_staged":already,
                "private_batch_verified":True,"verified_products":len(products),
                "verified_parts":proven["shards_verified"],
                "source_files_verified":proven["files_reconstructed"],
                "scientific_dossiers_independently_approved":0,
                "legal_rights_dossiers_independently_approved":0,
                "independent_domain_approvals":0,"owner_release_approvals":0,
                "publications":0,"sales":0}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--inbox",required=True)
    p.add_argument("--store-db",required=True)
    p.add_argument("--limit",type=int,default=6)
    p.add_argument("--verified-private-shard-batch")
    p.add_argument("--private-shard-verifier")
    a=p.parse_args()
    if a.verified_private_shard_batch:
        if not a.private_shard_verifier:
            raise ValueError("PRIVATE_SHARD_VERIFIER_REQUIRED")
        result=import_verified_private_shards(a.verified_private_shard_batch,
                                              a.store_db,a.private_shard_verifier)
        print("ZOMOROD_OFFICIAL_PRIVATE_SHARD_STORE="+json.dumps(result,sort_keys=True))
        print("ZOMOROD_SHARD_OWNER_APPROVAL=NOT_GRANTED")
    else:
        result=import_catalog(a.inbox,a.store_db,a.limit)
        print("ZOMOROD_BRIDGE_PRIVATE_CATALOG="+json.dumps(result,sort_keys=True))
    print("ZOMOROD_BRIDGE_PUBLIC_ACTIVATIONS=0")
    print("ZOMOROD_BRIDGE_FAKE_PRICES=0")


if __name__=="__main__":
    try:main()
    except (ValueError,RuntimeError,OSError,sqlite3.Error,zipfile.BadZipFile) as e:
        print("ZOMOROD_BRIDGE_IMPORT_FAILED="+type(e).__name__,file=sys.stderr)
        sys.exit(1)
