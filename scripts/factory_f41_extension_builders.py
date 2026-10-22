#!/usr/bin/env python3
"""F41 advanced OFFLINE prototype builders. No network, private keys, signatures, or transfers.

These are candidate engineering utilities. They are NOT audited deployable
financial contracts, live indexers, legal opinions or exchange liquidity.
"""
import csv
import hashlib
import io
import json
import re

KINDS = (
    "trc721_collection", "trc1155_inventory", "staking_simulator",
    "dao_vote", "escrow_milestones", "watch_wallet_sdk",
    "onchain_indexer", "chain_analytics", "royalty_accounting",
    "certificate_verifier_api", "rights_marketplace", "bridge_risk",
    "contract_fuzz", "security_monitor", "rwa_eligibility",
)
NAME = re.compile(r"[a-zA-Z][a-zA-Z0-9_.-]{1,63}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
TRON = re.compile(r"T[1-9A-HJ-NP-Za-km-z]{33}\Z")
ACCOUNT = re.compile(r"[a-zA-Z0-9_.-]{2,64}\Z")


def fail(code):
    raise ValueError("F41_EXTENSION_" + code)


def exact(data, keys):
    if type(data) is not dict or set(data) != set(keys):
        fail("FIELDS")


def bounded_list(value, maximum=100, minimum=1):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        fail("LIST_BOUNDS")
    return value


def tag(value):
    if type(value) is not str or not NAME.fullmatch(value):
        fail("INVALID_TAG")
    return value


def account(value):
    if type(value) is not str or not ACCOUNT.fullmatch(value):
        fail("INVALID_ACCOUNT")
    return value


def uint(value, upper=10**30, allow_zero=True):
    if (type(value) is not str or not re.fullmatch(r"(?:0|[1-9][0-9]{0,29})", value)):
        fail("INVALID_UINT")
    n = int(value)
    if n > upper or (not allow_zero and n == 0):
        fail("UINT_RANGE")
    return n


def index(value):
    if type(value) is not int or not 0 <= value <= 10**9:
        fail("INVALID_INDEX")
    return value


def verified_hex(value):
    if type(value) is not str or not HEX.fullmatch(value):
        fail("INVALID_HASH")
    return value


def blob(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf8")


def table(rows):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerows(rows)
    return out.getvalue().encode("utf8")


def trc721_collection(d, asset_root, read_asset):
    exact(d, ("collection", "symbol", "items"))
    collection = tag(d["collection"])
    symbol = tag(d["symbol"])
    ids = set()
    output = []
    for row in bounded_list(d["items"]):
        exact(row, ("token_id", "owner_ref", "asset_file"))
        ident = index(row["token_id"])
        if ident in ids:
            fail("DUPLICATE_TOKEN")
        ids.add(ident)
        asset = read_asset(asset_root, row["asset_file"])
        output.append({"token_id": ident, "owner_ref": account(row["owner_ref"]),
                       "media_sha256": hashlib.sha256(asset).hexdigest(),
                       "media_bytes": len(asset)})
    return {"trc721-collection.json": blob({
        "collection": collection, "symbol": symbol, "inventory": sorted(output, key=lambda x: x["token_id"]),
        "standard_target": "TRC-721", "deployment_executed": False,
        "safe_transfer_contract_verified": False, "chain_minted": False,
        "buyer_use": "reproducible unique collectible inventory and asset binding"})}


def trc1155_inventory(d, asset_root, read_asset):
    exact(d, ("collection", "items"))
    collection = tag(d["collection"])
    ids, output = set(), []
    for row in bounded_list(d["items"]):
        exact(row, ("token_id", "quantity", "asset_file"))
        ident = index(row["token_id"])
        quantity = uint(row["quantity"], allow_zero=False)
        if ident in ids:
            fail("DUPLICATE_TOKEN")
        ids.add(ident)
        media = read_asset(asset_root, row["asset_file"])
        output.append({"id": ident, "supply_base_units": str(quantity),
                       "media_sha256": hashlib.sha256(media).hexdigest()})
    return {"trc1155-inventory.json": blob({
        "collection": collection, "standard_target": "TRC-1155",
        "items": sorted(output, key=lambda x: x["id"]), "total_units": str(sum(int(x["supply_base_units"]) for x in output)),
        "contract_deployed": False, "batch_transfer_tested": False})}


def staking_simulator(d, unused, read_asset):
    exact(d, ("apr_basis_points", "days", "positions"))
    apr = index(d["apr_basis_points"])
    days = index(d["days"])
    if not 1 <= days <= 3650 or apr > 100000:
        fail("STAKING_BOUNDS")
    seen, report = set(), []
    for row in bounded_list(d["positions"]):
        exact(row, ("account", "principal_base_units"))
        name = account(row["account"])
        principal = uint(row["principal_base_units"], allow_zero=False)
        if name in seen:
            fail("DUPLICATE_ACCOUNT")
        seen.add(name)
        reward = (principal * apr * days) // (365 * 10000)
        report.append({"account": name, "principal": str(principal), "hypothetical_reward": str(reward)})
    return {"staking-simulation.json": blob({
        "apr_basis_points": apr, "days": days, "records": sorted(report, key=lambda x:x["account"]),
        "total_reward": str(sum(int(x["hypothetical_reward"]) for x in report)),
        "reward_funded": False, "staking_contract": False, "guaranteed_yield": False})}


def dao_vote(d, unused, read_asset):
    exact(d, ("proposal_id", "quorum_base_units", "snapshot", "votes"))
    pid = tag(d["proposal_id"])
    quorum = uint(d["quorum_base_units"], allow_zero=False)
    weights = {}
    for row in bounded_list(d["snapshot"]):
        exact(row, ("voter", "weight"))
        voter = account(row["voter"])
        if voter in weights:
            fail("DUPLICATE_SNAPSHOT")
        weights[voter] = uint(row["weight"], allow_zero=False)
    used = set()
    tally = {"yes": 0, "no": 0, "abstain": 0}
    for row in bounded_list(d["votes"], minimum=0):
        exact(row, ("voter", "choice"))
        voter = account(row["voter"])
        choice = row["choice"]
        if voter not in weights or voter in used or choice not in tally:
            fail("INVALID_VOTE")
        used.add(voter)
        tally[choice] += weights[voter]
    participated = sum(tally.values())
    return {"dao-tally.json": blob({
        "proposal_id": pid, "snapshot_total": str(sum(weights.values())),
        "participation": str(participated), "weighted_votes": {k: str(v) for k,v in tally.items()},
        "quorum_reached": participated >= quorum,
        "passed_offchain": participated >= quorum and tally["yes"] > tally["no"],
        "governance_executed_onchain": False})}


def escrow_milestones(d, unused, read_asset):
    exact(d, ("escrow_ref", "total_base_units", "milestones"))
    ref = tag(d["escrow_ref"])
    total = uint(d["total_base_units"], allow_zero=False)
    seen, rows, allocation = set(), [], 0
    for row in bounded_list(d["milestones"]):
        exact(row, ("id", "amount_base_units", "approval_evidence_sha256"))
        ident = tag(row["id"])
        if ident in seen:
            fail("DUPLICATE_MILESTONE")
        seen.add(ident)
        amount = uint(row["amount_base_units"], allow_zero=False)
        allocation += amount
        rows.append({"id": ident, "amount_base_units": str(amount),
                     "evidence_sha256": verified_hex(row["approval_evidence_sha256"]),
                     "release_authorized": False})
    if allocation > total:
        fail("ESCROW_OVERALLOCATED")
    return {"escrow-plan.json": blob({
        "escrow_ref": ref, "total": str(total), "allocated": str(allocation),
        "unallocated": str(total-allocation), "milestones": rows,
        "funds_custodied": False, "contract_deployed": False, "disbursements": 0})}


WATCH_ONLY_SDK = '''"""Tron watch-only address checksum verifier. NEVER signs, derives or transmits."""
import hashlib

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def verify_tron_address(address):
    if not isinstance(address, str) or len(address) != 34 or not address.startswith("T"):
        return False
    n = 0
    for ch in address:
        if ch not in ALPHABET:
            return False
        n = n * 58 + ALPHABET.index(ch)
    raw = n.to_bytes(25, "big") if n < 256**25 else b""
    if len(raw) != 25 or raw[0] != 0x41:
        return False
    payload, checksum = raw[:21], raw[21:]
    first = hashlib.sha256(payload).digest()
    return hashlib.sha256(first).digest()[:4] == checksum
'''


def watch_wallet_sdk(d, unused, read_asset):
    exact(d, ("addresses",))
    rows, seen = [], set()
    for value in bounded_list(d["addresses"]):
        if type(value) is not str or not TRON.fullmatch(value) or value in seen:
            fail("INVALID_WATCH_ADDRESS")
        seen.add(value)
        rows.append(value)
    # These inputs are not treated as verified until run by the generated SDK.
    return {"watch_wallet.py": WATCH_ONLY_SDK.encode("utf8"),
            "watch-config.json": blob({
                "addresses": sorted(rows), "operation": "read_only",
                "address_checksum_verification": "runtime_function",
                "private_keys_handled": False, "chain_reads_performed": 0,
                "transactions_signed": 0})}


def onchain_indexer(d, unused, read_asset):
    exact(d, ("network", "events"))
    if d["network"] not in ("shasta", "nile", "tron_mainnet_observed_only"):
        fail("NETWORK")
    identifiers, final = set(), []
    for row in bounded_list(d["events"], maximum=500):
        exact(row, ("txid", "log_index", "block_height", "event", "block_hash"))
        txid = verified_hex(row["txid"])
        block = verified_hex(row["block_hash"])
        li = index(row["log_index"])
        height = index(row["block_height"])
        identifier = (txid, li)
        if identifier in identifiers:
            fail("DUPLICATE_LOG_ID")
        identifiers.add(identifier)
        final.append({"txid": txid, "log_index": li, "block_height": height,
                      "block_hash": block, "event": tag(row["event"])})
    final.sort(key=lambda x:(x["block_height"],x["log_index"],x["txid"]))
    return {"event-index.json": blob({
        "network": d["network"], "indexed": final,
        "independent_node_proof": False, "canonical_chain_verified": False,
        "reorg_reconciliation_required": True})}


def chain_analytics(d, unused, read_asset):
    exact(d, ("transfers",))
    totals, grand = {}, 0
    for row in bounded_list(d["transfers"], maximum=500):
        exact(row, ("source", "destination", "amount_base_units"))
        sender, receiver = account(row["source"]), account(row["destination"])
        amount = uint(row["amount_base_units"], allow_zero=False)
        for who, direction in ((sender, "outbound"), (receiver,"inbound")):
            entry = totals.setdefault(who, {"inbound": 0, "outbound": 0})
            entry[direction] += amount
        grand += amount
    return {"chain-analysis.json": blob({
        "accounts": [{"id":k, **{x: str(y) for x,y in v.items()}} for k,v in sorted(totals.items())],
        "gross_transfer_base_units": str(grand), "source": "customer_supplied_observations",
        "independently_verified_onchain": False, "investment_advice": False})}


def royalty_accounting(d, unused, read_asset):
    exact(d, ("sales", "payees"))
    shares, seen = {}, set()
    for row in bounded_list(d["payees"]):
        exact(row, ("id", "basis_points"))
        ident = account(row["id"])
        bp = index(row["basis_points"])
        if ident in seen or bp > 10000:
            fail("ROYALTY_SHARES")
        shares[ident] = bp
        seen.add(ident)
    if sum(shares.values()) != 10000:
        fail("ROYALTY_SHARES_NOT_10000")
    ledger, total, sale_ids = {name:0 for name in shares}, 0, set()
    for row in bounded_list(d["sales"], maximum=500):
        exact(row, ("sale_id", "net_base_units"))
        name = tag(row["sale_id"])
        amount = uint(row["net_base_units"], allow_zero=False)
        if name in sale_ids:
            fail("DUPLICATE_SALE")
        sale_ids.add(name)
        total += amount
        assigned = 0
        members = sorted(shares)
        for recipient in members[:-1]:
            share = amount * shares[recipient] // 10000
            ledger[recipient] += share
            assigned += share
        ledger[members[-1]] += amount-assigned
    if sum(ledger.values()) != total:
        fail("ROYALTY_CONSERVATION")
    return {"royalty-ledger.csv": table([["payee", "due_base_units"]] + [[k,str(v)] for k,v in sorted(ledger.items())]),
            "royalty-control.json": blob({
                "sale_count": len(d["sales"]), "total_net": str(total),
                "royalty_allocated": str(sum(ledger.values())),
                "transfers_executed": 0, "rights_verified": False})}


VERIFIER_API = '''"""Local-only hash certificate verification endpoint, no claim of legal ownership."""
import hashlib
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/verify":
            self.send_error(404)
            return
        raw_length = self.headers.get("Content-Length", "0")
        if not raw_length.isdecimal() or int(raw_length) > 131072:
            self.send_error(413)
            return
        try:
            payload = json.loads(self.rfile.read(int(raw_length)))
            actual = hashlib.sha256(bytes.fromhex(payload["content_hex"])).hexdigest()
            expected = payload["expected_sha256"]
            passed = isinstance(expected,str) and len(expected)==64 and hmac.compare_digest(actual,expected)
            response = json.dumps({"matches":passed, "ownership_certified":False}).encode()
        except (ValueError, TypeError, KeyError, OverflowError):
            self.send_error(400)
            return
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(response)))
        self.end_headers()
        self.wfile.write(response)

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
'''


def certificate_verifier_api(d, unused, read_asset):
    exact(d, ("expected_sha256", "document_name"))
    return {"certificate_api.py": VERIFIER_API.encode(),
            "certificate-config.json": blob({
                "expected_sha256": verified_hex(d["expected_sha256"]),
                "document_name": tag(d["document_name"]),
                "bind_address": "127.0.0.1:8765", "legal_certification": False,
                "certificate_issuer_authenticated": False})}


def rights_marketplace(d, asset_root, read_asset):
    exact(d, ("listings",))
    seen, result = set(), []
    for row in bounded_list(d["listings"]):
        exact(row, ("listing_id", "asset_file", "license_label", "price_minor", "currency"))
        ident = tag(row["listing_id"])
        if ident in seen:
            fail("DUPLICATE_LISTING")
        seen.add(ident)
        media = read_asset(asset_root, row["asset_file"])
        currency = row["currency"]
        if currency not in ("USD", "EUR"):
            fail("CURRENCY")
        result.append({"listing_id": ident, "asset_sha256": hashlib.sha256(media).hexdigest(),
                       "claimed_license": tag(row["license_label"]), "price_minor": str(uint(row["price_minor"],allow_zero=False)),
                       "currency": currency, "copyright_verified": False})
    return {"marketplace-catalog.json": blob({
        "private_listings": sorted(result,key=lambda x:x["listing_id"]),
        "publicly_listed": False, "orders_taken": 0, "sales_verified": 0})}


def bridge_risk(d, unused, read_asset):
    exact(d, ("messages",))
    seen, records = set(), []
    for row in bounded_list(d["messages"]):
        exact(row, ("source_chain", "destination_chain", "nonce", "message_hash", "proof_hash"))
        source, dest = tag(row["source_chain"]), tag(row["destination_chain"])
        nonce = index(row["nonce"])
        if source == dest:
            fail("SAME_CHAIN")
        key = (source, dest, nonce)
        if key in seen:
            fail("BRIDGE_REPLAY")
        seen.add(key)
        records.append({"source":source, "destination":dest, "nonce":nonce,
                        "message_sha256":verified_hex(row["message_hash"]),
                        "claimed_proof_sha256":verified_hex(row["proof_hash"]),
                        "proof_independently_verified":False, "bridge_release_authorized":False})
    return {"bridge-risk-report.json": blob({
        "messages":records,"duplicate_nonce_count":0,
        "light_client_verified":False,"funds_unlocked":False,
        "security_audit_certified":False})}


FUZZ_HARNESS = '''"""Seeded offline vesting conservation property test; NOT EVM fuzzing."""
import random

def run(seed=41, rounds=10000):
    gen=random.Random(seed)
    for _ in range(rounds):
        amount=gen.randint(1,10**18)
        periods=gen.randint(1,120)
        part,remainder=divmod(amount,periods)
        payouts=[part]*(periods-1)+[part+remainder]
        assert sum(payouts)==amount
        assert all(x>=0 for x in payouts)
    return rounds

if __name__ == "__main__":
    print("F41_OFFLINE_PROPERTY_CHECKS="+str(run()))
'''


def contract_fuzz(d, unused, read_asset):
    exact(d, ("seed", "rounds"))
    seed, rounds = index(d["seed"]), index(d["rounds"])
    if not 1 <= rounds <= 100000:
        fail("FUZZ_ROUNDS")
    return {"fuzz_vesting.py": FUZZ_HARNESS.replace("def run(seed=41, rounds=10000):", f"def run(seed={seed}, rounds={rounds}):").encode("utf8"),
            "fuzz-config.json": blob({
                "seed":seed,"rounds":rounds,
                "coverage": "integer vesting conservation only",
                "evm_bytecode_executed":False, "audit_completed":False})}


def security_monitor(d, unused, read_asset):
    exact(d, ("alert_threshold_base_units", "allowed_recipients", "observations"))
    threshold=uint(d["alert_threshold_base_units"], allow_zero=False)
    allowed=set()
    for v in bounded_list(d["allowed_recipients"]):
        allowed.add(account(v))
    alerts=[]
    for row in bounded_list(d["observations"],maximum=500):
        exact(row, ("txid", "recipient", "amount_base_units"))
        transaction=verified_hex(row["txid"])
        recipient=account(row["recipient"])
        amount=uint(row["amount_base_units"])
        reasons=[]
        if amount>=threshold: reasons.append("LARGE_TRANSFER")
        if recipient not in allowed: reasons.append("UNKNOWN_RECIPIENT")
        if reasons: alerts.append({"txid":transaction, "reasons":reasons})
    return {"alerts.json": blob({
        "alerts": alerts, "threshold":str(threshold),"input_data_authenticated":False,
        "notifications_sent":0,"live_blockchain_connection":False})}


def rwa_eligibility(d, asset_root, read_asset):
    exact(d, ("asset_ref", "jurisdiction", "documents", "checklist"))
    item=tag(d["asset_ref"])
    jur=tag(d["jurisdiction"])
    docs=[]
    for file in bounded_list(d["documents"]):
        payload=read_asset(asset_root,file)
        docs.append({"file":file,"sha256":hashlib.sha256(payload).hexdigest()})
    checklist=d["checklist"]
    exact(checklist, ("issuer_identified", "ownership_documents_reviewed",
                      "transfer_restrictions_reviewed", "regulated_offering_reviewed"))
    if any(type(v) is not bool for v in checklist.values()):
        fail("RWA_CHECKLIST_BOOLEAN")
    return {"rwa-evidence.json": blob({
        "asset_ref":item,"jurisdiction":jur,"documents":sorted(docs,key=lambda x:x["file"]),
        "claimant_checklist":checklist, "human_legal_verification":"NOT_PERFORMED",
        "compliance_approved":False,"tokenization_authorized":False})}


BUILDERS = {
    "trc721_collection": trc721_collection,
    "trc1155_inventory": trc1155_inventory,
    "staking_simulator": staking_simulator,
    "dao_vote": dao_vote,
    "escrow_milestones": escrow_milestones,
    "watch_wallet_sdk": watch_wallet_sdk,
    "onchain_indexer": onchain_indexer,
    "chain_analytics": chain_analytics,
    "royalty_accounting": royalty_accounting,
    "certificate_verifier_api": certificate_verifier_api,
    "rights_marketplace": rights_marketplace,
    "bridge_risk": bridge_risk,
    "contract_fuzz": contract_fuzz,
    "security_monitor": security_monitor,
    "rwa_eligibility": rwa_eligibility,
}


def render(mode, data, asset_root, read_asset):
    if mode not in KINDS:
        fail("UNKNOWN_KIND")
    result = BUILDERS[mode](data, asset_root, read_asset)
    if (not result or len(result) > 20 or any(not NAME.fullmatch(k) for k in result)
            or any(type(v) is not bytes or len(v) > 250000 for v in result.values())):
        fail("OUTPUT_INVALID")
    return result
