#!/usr/bin/env python3
"""Produce source-bound, format-screened PRIVATE review previews of native goods.

This is NOT buyer functional acceptance, scientific peer review, rights clearance,
a public download, or a commercial product release. No source modification.
"""
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

SCHEMA = "saeit.factory.native-source-review-package.v1"


def _private(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("NATIVE_PREVIEW_SYMLINK_DIRECTORY")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("NATIVE_PREVIEW_UNSAFE_DIRECTORY")
    os.chmod(path, 0o700)
    return path


def _blob(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2)+"\n").encode("utf8")


def pack(root, product, version, manifest, original, courier):
    root = Path(root)
    if not courier.RECIPE.fullmatch(product) or not courier.SHA.fullmatch(version):
        raise ValueError("NATIVE_PREVIEW_BAD_SOURCE_ID")
    courier.verify_stock(manifest, product, version, original)
    # Static verification is independently repeated by the recipient courier.
    audit = courier.native_format_census(original)
    family = manifest.get("family_id")
    if not isinstance(family, str) or not family.startswith("F") or not family[1:].isdigit():
        family = None
    target = root/"customer-packs"/product/version
    if target.is_symlink():
        raise ValueError("NATIVE_PREVIEW_SYMLINK_TARGET")
    if target.exists():
        old = courier.customer_companion(root,product,version,manifest["artifact_sha256"])
        if not old or old[0].get("schema")!=SCHEMA:
            raise ValueError("NATIVE_PREVIEW_EXISTING_CANDIDATE_CONFLICT")
        return dict(old[0],new=False)
    parent = _private(root/"customer-packs"/product)
    stage = Path(tempfile.mkdtemp(dir=parent,prefix=".native-private-"))
    try:
        _private(stage)
        guide = (
            "# Private native product review — "+product+"\n\n"
            "**NOT APPROVED FOR SALE OR PUBLIC DOWNLOAD.**\n\n"
            "The deliverable is `product/ORIGINAL_FACTORY_PRODUCT.zip`, a byte-for-byte "
            "copy of the original hash-verified factory ZIP. Extract this inner ZIP "
            "to inspect the real native documents or media. No content or source "
            "software was rewritten or independently executed by this review pack.\n\n"
            "The file types and syntax/signatures were inspected without executing "
            "any included Python or JavaScript. Functional operation, specialist "
            "quality, intellectual property, third-party licenses, commercial "
            "suitability and owner approval remain **unverified**.\n\n"
            "Inspect `qa/NATIVE_STRUCTURE_QA.json` and SHA256SUMS before accepting "
            "any goods, and require separate specialist reviews for every format.\n"
        ).encode("utf8")
        license_hold = (
            "NOT LICENSED FOR PUBLIC RESALE OR DISTRIBUTION.\n"
            "Native source ownership, third-party asset licenses, specialist "
            "functional reviews and explicit owner release permission "
            "are still required.\n"
        ).encode("utf8")
        qa = _blob({
            "schema":"saeit.factory.native-source-static-qa.v1",
            "product_id":product,
            "original_source_sha256":version,
            "original_artifact_sha256":manifest["artifact_sha256"],
            "native_formats":audit,
            "original_archive_preserved":True,
            "human_expert_reviewed":False,
            "functional_or_domain_qa_verified":False,
            "rights_and_license_cleared":False,
            "commercial_release":False
        })
        files = {
            "product/ORIGINAL_FACTORY_PRODUCT.zip":original,
            "guide/START_HERE.md":guide,
            "license/REVIEW_REQUIRED.txt":license_hold,
            "qa/NATIVE_STRUCTURE_QA.json":qa,
        }
        checksum = "".join(courier.digest(raw)+"  "+name+"\n"
                           for name,raw in sorted(files.items())).encode("utf8")
        files["qa/SHA256SUMS.txt"] = checksum
        packfile = stage/"customer-package.zip"
        with zipfile.ZipFile(packfile,"w",compression=zipfile.ZIP_STORED,allowZip64=False) as z:
            for name,body in sorted(files.items()):
                info=zipfile.ZipInfo(name,(2020,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_STORED
                info.external_attr=0o100644<<16
                z.writestr(info,body)
        data=packfile.read_bytes()
        if not 0<len(data)<=courier.MAX_ZIP:
            raise ValueError("NATIVE_PREVIEW_PACKAGE_LIMIT")
        report={
            "schema":SCHEMA, "product_id":product, "family_id":family,
            "factory_source_sha256":version,
            "factory_internal_zip_sha256":manifest["artifact_sha256"],
            "native_structural_review_passed":True,
            "native_source_file_count":audit["inspected_members"],
            "native_source_formats":audit["format_counts"],
            "technical_buyer_package_verified":False,
            "consumer_cli_smoke_examples_passed":0,
            "independent_domain_review_completed":False,
            "rights_and_license_review_completed":False,
            "human_attestation_completed":False,
            "eligible_for_commercial_listing":False,
            "commercial_release":False,
            "public_download_allowed":False,
            "price":None,
            "package_sha256":courier.digest(data),
            "package_bytes":len(data),
            "requires_native_specialist_and_owner_review":True,
            "review_scope":"original source preserved; static format checks only"
        }
        courier.verify_native_private_preview(report,data,product,version,manifest["artifact_sha256"])
        mpath=stage/"candidate_manifest.json"
        mpath.write_bytes(_blob(report))
        os.chmod(mpath,0o600)
        os.chmod(packfile,0o400)
        os.replace(stage,target)
        return dict(report,new=True)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
