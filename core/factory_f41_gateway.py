"""F41 private production tool for the authenticated moj_1ro_1 AgentTask runtime.

Never accepts caller-controlled paths, networks, credentials, or site endpoints.
The only effect is building and verifying a bounded private work order.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

ACTION = "factory_f41_private_build"
ORDER = re.compile(r"F41-[a-z0-9-]{3,56}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
KINDS = ("vesting", "reconciliation", "provenance", "nft_metadata")


def _safe_dir(path):
    if path.is_symlink() or not path.is_dir():
        raise ValueError("F41_MASTER_UNSAFE_DIRECTORY")
    return path


def roots():
    base = _safe_dir(Path.home() / "factory-runtime")
    ops = _safe_dir(base / "operations")
    _safe_dir(ops / "f41-multiproduct")
    private = _safe_dir(base / "private")
    cycle = _safe_dir(private / "autonomous-product-cycle")
    root = _safe_dir(cycle / "f41-multiproduct")
    return root, ops / "f41-multiproduct"


def factory_module(ops):
    source = ops / "factory_f41_multi_product_builder.py"
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 100000:
        raise ValueError("F41_MASTER_SOURCE_UNTRUSTED")
    spec = importlib.util.spec_from_file_location("f41_installed_private_builder", str(source))
    if spec is None or spec.loader is None:
        raise ValueError("F41_MASTER_BUILDER_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validated_order(root, ops, name, expected_hash=None):
    if type(name) is not str or not ORDER.fullmatch(name):
        raise ValueError("F41_MASTER_ORDER_ID_INVALID")
    file = _safe_dir(root / "orders") / (name + ".json")
    if file.is_symlink() or not file.is_file() or file.stat().st_size > 150000:
        raise ValueError("F41_MASTER_ORDER_FILE_UNSAFE")
    raw = file.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_hash is not None and digest != expected_hash:
        raise ValueError("F41_MASTER_ORDER_REVISION_CHANGED")
    builder = factory_module(ops)
    request = builder.read_request(file)
    if request["kind"] not in KINDS:
        raise ValueError("F41_MASTER_UNAUTHORIZED_KIND")
    assets = _safe_dir(ops / "assets")
    # Parse and validate the entire request, including local-asset content,
    # before writing an AgentTask or output.
    builder.payload(request, assets)
    return file, request, digest, builder, assets


def inspect_order(root, ops, order_id):
    _, request, digest, _, _ = validated_order(root, ops, order_id)
    return {"order_id": order_id, "kind": request["kind"],
            "product_id": request["product_id"], "request_sha256": digest}


def build_verified_order(payload):
    if os.getenv("MOJ_FACTORY_LOCAL_MODE") != "1":
        raise ValueError("F41_MASTER_PRIVATE_VPS_ONLY")
    if type(payload) is not dict or set(payload) != {
            "order_id", "kind", "product_id", "request_sha256"}:
        raise ValueError("F41_MASTER_BOUND_PAYLOAD_REQUIRED")
    h = payload["request_sha256"]
    if type(h) is not str or not HASH.fullmatch(h):
        raise ValueError("F41_MASTER_ORDER_DIGEST_INVALID")
    root, ops = roots()
    file, request, digest, builder, assets = validated_order(
        root, ops, payload["order_id"], h)
    if request["kind"] != payload["kind"] or request["product_id"] != payload["product_id"]:
        raise ValueError("F41_MASTER_ORDER_IDENTITY_CHANGED")
    output_base = _safe_dir(root / "outputs")
    output = output_base / payload["order_id"]
    if output.is_symlink():
        raise ValueError("F41_MASTER_OUTPUT_SYMLINK")
    receipt = (builder.verify(file, output, assets) if output.exists()
               else builder.build(file, output, assets))
    expected = builder.manifest(request, builder.payload(request, assets))
    if receipt != expected or receipt["quality_1000_certified"] is not False:
        raise ValueError("F41_MASTER_PRODUCT_RECEIPT_INVALID")
    manifest_path = output / "manifest.json"
    return {
        "verified_effect": True, "family": "F41", "kind": request["kind"],
        "product_id": request["product_id"], "order_id": payload["order_id"],
        "request_sha256": digest,
        "product_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "technical_product_created": True,
        "master_verified_task_execution": True,
        "next_action": "independent_security_market_and_commercial_validation",
        "quality_1000_certified": False,
        "commercial_release": False, "liquidity_proven": False,
        "website_mutations": 0, "mainnet_transactions": 0, "financial_actions": 0,
    }
