#!/usr/bin/env python3
"""Separates 40-family MojPlayWin crypto and Zomorod Bank Shahr merchant rails.

Writes only offline private evidence-bound payment routing proposals; NEVER
activates checkout, authorizes paid content, or calls merchant endpoints.
Bank Shahr is the account/acquirer specified by owner; its PSP API is unknown.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

SCHEMA="saeit.factory.two-site-merchant-rails.v1"
ID=re.compile(r"^F(?:0[1-9]|[1-3][0-9]|40)$")
SITES={
 "mojplaywin":{
   "host":"mojplaywin.com",
   "rail":"existing_mojplaywin_crypto_gateway",
   "settlement_type":"on_chain",
   "settlement_currency_options":["TRX","ETH"],
   "chain_receipt_requirements":[
     "verify on-chain transfer to verified controlled wallet",
     "match chain identifier asset token contract and transaction hash",
     "verify address ownership and unique invoice wallet attribution",
     "check amount quote expiry and adequate confirmations using trusted RPC",
     "reject replayed or reorganized on-chain transactions",
     "securely issue individual digital fulfillment only after final settlement"],
   "owner_named_existing_gateway":True,
   "actual_gateway_config_read_from_site":False},
 "zomorodmelal":{
   "host":"zomorodmelal.ir",
   "rail":"bank_shahr_linked_iranian_ipg",
   "settlement_type":"bank_psp_server_to_server_verify",
   "settlement_currency_options":["IRR"],
   "bank_account_provider":"Bank Shahr",
   "psp_provider":"not_yet_verified",
   "settlement_receipt_requirements":[
     "identify actual licensed PSP and bank-linked merchant and terminal identity",
     "obtain PSP supplied verified API and approved callback domains",
     "verify merchant and amount order identifier via authenticated backend",
     "server-to-server verify capture/reference result against PSP official endpoint",
     "enforce atomic idempotency refund and chargeback reversal",
     "grant expiring authenticated digital fulfillment only for settled order"],
   "owner_named_existing_gateway":True,
   "actual_gateway_config_read_from_site":False},
}
ROUTES=("digital_license","business_license","custom_service_quote")
def ensure(ok,code):
    if not ok:raise ValueError("MERCHANT_RAILS_"+code)
def data_hash(value):
    raw=json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf8")
    return hashlib.sha256(raw).hexdigest()
def private(path):
    p=Path(path)
    ensure(not p.is_symlink(),"SYMLINK")
    p.mkdir(parents=True,exist_ok=True,mode=0o700)
    ensure(p.is_dir() and not p.is_symlink(),"BAD_PRIVATE_DIRECTORY")
    os.chmod(p,0o700)
    return p
def load(path,limit=220000):
    p=Path(path)
    ensure(p.is_file() and not p.is_symlink() and 0<p.stat().st_size<=limit,
           "SOURCE_UNTRUSTED")
    value=json.loads(p.read_text("utf8"))
    ensure(isinstance(value,dict),"SOURCE_NOT_OBJECT")
    return value
def write(path,obj):
    p=Path(path);private(p.parent)
    ensure(not p.is_symlink(),"SYMLINK_OUTPUT")
    raw=(json.dumps(obj,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode("utf8")
    if p.is_file() and p.read_bytes()==raw:return False
    fd,name=tempfile.mkstemp(dir=str(p.parent),prefix=".rails-")
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.chmod(name,0o600)
        os.replace(name,p)
    finally:
        if os.path.exists(name):os.unlink(name)
def normalize_site(raw):
    ensure(isinstance(raw,str) and raw in SITES,"UNKNOWN_SITE")
    return raw
def assert_origin(site,origin):
    """Never redirect from inbound client-provided host, bank endpoint, or wallet."""
    key=normalize_site(site)
    u=urlsplit(origin) if isinstance(origin,str) else None
    ensure(u is not None and u.scheme=="https" and u.hostname==SITES[key]["host"]
      and not u.username and not u.password and u.port in (None,443)
      and not u.query and not u.fragment and u.path in ("","/"),"INVALID_SITE_ORIGIN")
    return key
def verify_policy(merchant,product,offer):
    site=normalize_site(merchant)
    ensure(type(product) is str and ID.fullmatch(product),"BAD_FAMILY")
    ensure(offer.get("family_id")==product,"CROSS_FAMILY_OFFER")
    ensure(offer.get("offer_status")=="commercial_preparation_private_only" and
      offer.get("public_sale_allowed") is False and
      offer.get("payment_enabled") is False and
      offer.get("published") is False,"INVALID_COMMERCIAL_STATE")
    blocking=offer.get("commercial_blockers")
    ensure(isinstance(blocking,list) and len(blocking)>0,"MISSING_COMMERCE_BLOCKERS")
    return site
def rail_route(site,fid,offer):
    key=verify_policy(site,fid,offer)
    bank=SITES[key]
    return {"schema":SCHEMA,"site_id":key,"site_host":bank["host"],
       "family_id":fid,"sku":offer.get("sku"),
       "product_categories":list(ROUTES),
       "technical_file_portfolio_exists":
          offer.get("technical_products_with_verified_archive",0)>0,
       "technical_package_count":offer.get("technical_products_with_verified_archive",0),
       "merchant_rail":bank["rail"],"settlement_type":bank["settlement_type"],
       "declared_seller_type":"natural_person_owner_not_company",
       "declared_seller_professional_name":"مجتبی روزگار",
       "legal_seller_identity_independently_verified":False,
       "merchant_gateway_contract_matches_declared_seller":False,
       "settlement_beneficiary_matches_declared_seller_verified":False,
       "company_role":"technology_and_sales_services_platform_not_ip_owner_or_assumed_merchant",
       "company_name":"شرکت کشت و صنعت زمرد ملل",
       "permitted_settlement_currencies":bank["settlement_currency_options"],
       "bank_account_provider":bank.get("bank_account_provider"),
       "psp_provider":bank.get("psp_provider"),
       "owner_specified_existing_gateway":True,
       "merchant_api_configuration_verified_on_live_site":False,
       "test_receipt_and_payment_reconciliation_verified":False,
       "human_rights_and_content_approval_verified":False,
       "owner_approved_fixed_price_verified":False,
       "tax_refund_and_delivery_terms_verified":False,
       "backend_settlement_verification_enabled_by_this_module":False,
       "public_buy_button_enabled":False,
       "collect_customer_payment":False,
       "automatic_paid_entitlement":False,
       "allowed_private_action":"record_internal_nonchargeable_offer_or_quote_request",
       "commercial_blockers":sorted(set(offer["commercial_blockers"]+
         ["EXACT_GATEWAY_PROVIDER_AND_MERCHANT_CONTRACT_NOT_VERIFIED_BY_FACTORY",
          "CUSTOMER_PAYMENT_AND_POSTPAYMENT_DELIVERY_E2E_NOT_VERIFIED"])),
       "rails_not_interchangeable":True}
def require_currency(site,currency):
    key=normalize_site(site)
    ensure(isinstance(currency,str) and currency in
      SITES[key]["settlement_currency_options"],"CURRENCY_SITE_MISMATCH")
    return currency
def reject_unverified_payment(route,external_receipt):
    """Deliberately no loophole: a client assertion is never settlement proof."""
    ensure(isinstance(route,dict) and route.get("schema")==SCHEMA,"ROUTE_INVALID")
    ensure(route.get("collect_customer_payment") is False and
        route.get("automatic_paid_entitlement") is False and
        route.get("public_buy_button_enabled") is False,"UNSAFE_PAY_STATE")
    raise ValueError("MERCHANT_RAILS_NO_AUTHENTICATED_PROVIDER_RECEIPT_VERIFIER")
def run(root):
    root=Path(root)
    ensure(root.is_dir() and not root.is_symlink(),"UNSAFE_FACTORY_ROOT")
    registry=load(root/"commercial40/dashboard.json",500000)
    ensure(registry.get("private_commercial_sku_proposals")==40 and
        registry.get("commercially_approved_families")==0,"BAD_COMMERCE_REGISTRY")
    offers={}
    for i in range(1,41):
        fid="F%02d"%i
        offer=load(root/"commercial40/offers"/(fid+".json"))
        verify_policy("mojplaywin",fid,offer)
        offers[fid]=offer
    output=private(root/"merchant-rails")
    rows=[]
    for site in ("mojplaywin","zomorodmelal"):
        for fid,offer in offers.items():
            route=rail_route(site,fid,offer)
            write(output/"routes"/site/(fid+".json"),route)
            rows.append({"family_id":fid,"site_id":site,
                "route_hash":data_hash(route),"merchant_rail":route["merchant_rail"],
                "currency":route["permitted_settlement_currencies"],
                "sale_enabled":route["collect_customer_payment"]})
    ensure(len(rows)==80 and len({(x["site_id"],x["family_id"]) for x in rows})==80,
           "INCOMPLETE_80_SITE_ROUTES")
    report={"schema":SCHEMA,
      "updated_utc":datetime.now(timezone.utc).isoformat(),
      "site_count":2,"family_count_per_site":40,
      "private_site_family_offer_routes":len(rows),
      "unique_payment_rail_types":2,
      "families_with_technical_source":registry.get("genuine_verified_product_families"),
      "families_without_technical_source":registry.get("families_without_trusted_package"),
      "bank_shahr_gateway_psp_verified":False,
      "mojplaywin_crypto_live_receipt_verification_verified_here":False,
      "fake_live_sales_or_payment_claims":0,
      "new_public_buy_buttons":0,"sites_changed":0,"live_charges":0,
      "merchant_routes":SITES,
      "route_records":rows}
    write(output/"dashboard.json",report)
    print("FACTORY_MERCHANT_TWO_SITE_ROUTING="+json.dumps({
      "private_site_family_offer_routes":len(rows),
      "sites":["mojplaywin","zomorodmelal"],
      "mojplaywin":SITES["mojplaywin"]["rail"],
      "zomorodmelal":SITES["zomorodmelal"]["rail"],
      "verified_bank_psp_live_checkout":False,
      "verified_crypto_chain_checkout":False,
      "commercial_sales_activated":0},sort_keys=True))
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument("--factory-private",required=True)
    arg=p.parse_args();run(arg.factory_private)
if __name__=="__main__":
    try:main()
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as error:
        print("FACTORY_MERCHANT_RAILS_ERROR="+type(error).__name__+":"+str(error)[:130])
        raise SystemExit(1)
