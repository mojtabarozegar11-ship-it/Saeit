#!/usr/bin/env python3
"""Five requested SECOND-ROUND replies to existing inbound supplier conversations only.

Non-binding requests for information. Run only in authorized corporate cPanel.
Never emails anyone unless a matching inbound supplier message is present in Maildir.
Idempotent on disk. Does not print recipient identities or correspondence.
"""
from __future__ import annotations
import email.utils
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

SENDER="moj_1ro_1@zomorodmelal.ir"
MAILDIR=Path.home()/"mail"/"zomorodmelal.ir"/"moj_1ro_1"
PRIVATE=Path.home()/".company-outreach-private"
CAMPAIGN="trade-five-inbound-supplier-followups-20261023"
CUTOFF=datetime(2026,10,20,tzinfo=timezone.utc).timestamp()
CLOSING="""This follow-up is solely an inquiry for technical and commercial information.
It does not constitute a purchase order, bank commitment, confirmed import qualification,
guaranteed order volume, exclusive agency, or acceptance of commercial terms.
Any future transaction requires satisfactory due diligence, legal and export/import
compliance screening, and separate written approval and contract.

Kind regards,
Trade Development Desk
Zomorod Melal Agro-Industry Company (Iran)
https://zomorodmelal.ir
moj_1ro_1@zomorodmelal.ir
"""
TARGETS=[
 {"key":"SUHUI", "address":"suhui@suhuimachine.com", "body":"""Dear Aaron,

Thank you for considering a 180-day usance letter of credit. We appreciate your clarification about the issuing bank and transport to Iran.

We are currently at a non-binding feasibility and sourcing stage. No issuing bank, L/C facility, purchase order or shipment route has yet been confirmed; please do not regard our inquiry as a financing commitment.

Could you advise:
1) Whether you could consider an irrevocable usance L/C subject to UCP 600, 180 days measured from which exact document/date, and whether bank confirmation is mandatory.
2) Your generally acceptable issuing/confirming bank eligibility requirements and the usual country/jurisdiction acceptance criteria, for assessment by our licensed bank. We are not requesting any bypass of sanctions, export controls or bank compliance.
3) Which of your plastic recycling lines you manufacture directly. Please provide two illustrative model/capacity options, machine-by-machine bill of materials, indicative EXW/FOB quotations, utilities, motor power, lead times, warranty and references. These are feasibility benchmarks only, not a requested purchase quantity.
4) Whether you have a compliant shipping solution to Iran, with the usual documentary and independent screening prerequisites, or whether shipment must be assessed only after the buyer and end use are identified.
5) Whether a nonexclusive agency or customer-by-customer supply partnership could be considered without an advance inventory purchase.

We will consult the relevant authorized bank and logistics/compliance providers independently before proposing any financial structure.

""" },
 {"key":"HUAXIAN", "address":"molly@steviachina.com", "body":"""Dear Molly,

Thank you for your product list and certificates. We are particularly interested in your factory-produced RA95%, RA97%, and STV95% (RA60%) grades for a possible lawful Iranian food-ingredient distribution partnership.

Regarding your question about embassy stamping of the Certificate of Origin and commercial invoice: we cannot yet confirm a universal yes/no. We are checking the current documentary requirement with an appropriately licensed Iranian customs broker and relevant authorities. Please provide your usual document set and quote any legalization costs as a separate optional line until that is confirmed.

For each of these three grades, could you send:
1) Indicative USD EXW and FOB prices at commercially practical volume tiers (for example 25 kg, 100 kg and 1 metric ton), and MOQ for a first-time customer.
2) Current specification sheet, lot-specific CoA, additives/carriers/allergens, food-grade and Halal certificate scope, shelf life and samples availability/cost.
3) Full legal names of the producing factory, contracting exporter and intended invoice beneficiary so we can match your factory and certificates accurately.
4) Indicative lead time, package size, carton/pallet details and confirmation whether a lawful sale/shipment to Iran is currently supported by your internal compliance team.
5) Whether nonexclusive local distribution or controlled trial orders are an option, with no minimum annual purchase guarantee.

No order quantity or payment method has been approved at this stage.

""" },
 {"key":"HKAY", "address":"agar@agar.cn", "body":"""Dear Ren,

Thank you for the GS1000 agar-agar quotation of USD 11.50/kg and the supporting CoA, Halal and other documents.

To allow an apples-to-apples commercial assessment, would you please clarify:
1) Which Incoterm and location are included in the USD 11.50/kg indication (EXW, FCA or FOB), the quotation validity date and currency.
2) MOQ, prices and sample availability for illustrative quantities of 1 kg (evaluation), 25 kg, 100 kg and 1 metric ton; please offer only tiers that your factory actually supports.
3) Current GS1000 technical specification, lot-specific CoA and method for gel-strength measurement, microbiological limits, shelf life, packaging and lead time.
4) Your precise legal contracting exporter name and Baolong manufacturer's registration name, as well as the legal entity names and scope shown on your food-safety/Halal certificates.
5) Whether your export/compliance team can support legal shipment to Iran and what documents, logistics and payment terms would be required.

This is a request for a nonbinding quotation, not an order.

""" },
 {"key":"BOEVAN", "address":"marketing@boevan.cn", "body":"""Dear David,

Thank you for sending Shanghai Boevan's packaging machinery catalogue.

We would like to evaluate a practical small or medium packaging project and the possibility of nonexclusive representation/service cooperation. Please provide a nonbinding comparison of two or three proven factory-manufactured standard machine configurations for packing DRY powders or granules in roughly 100 g–1 kg packages. A range such as 20–60 packages/min may be used as a reference scenario if available; it is NOT a final capacity or confirmed project.

Please specify:
1) Machine models, suitable products/film types, weighing/auger options, throughput ranges, utilities, 380V/50Hz compatibility, dimensions and layout.
2) Indicative itemized EXW/FOB prices, tooling and commissioning costs, shipment packing, production lead times and spare-parts kit.
3) Factory acceptance tests, installation/training arrangement, technical support for Iran and warranty boundaries.
4) Certificates and evidence of previous operating installations for the offered models.
5) Whether a nonexclusive referral/representation or after-sales partnership is possible without compulsory stock purchases or sales guarantees.

Any future purchase would be contingent upon verified end-user demand, a lawful import route and a separately approved contract.

""" },
 {"key":"ALLWIN", "address":"zhouyunpeng@hballwin.com", "body":"""Dear Mr. Zhou,

Thank you for your detailed Hubei Allwin hybrid-rice seed information, technical brochure and indication of a 25,000-kg commercial minimum order with the three price levels.

Our main interest at this point is scientific/agronomic feasibility, not an immediate commercial container order. We have not obtained an Iranian rice-seed import permit and will not request shipment before the applicable approvals and plant-quarantine requirements have been confirmed.

Could you please advise:
1) Whether your breeding/R&D team would consider a formal joint varietal evaluation or limited research cooperation, with sample quantity and terms only after the necessary regulatory clearances.
2) Variety-specific dossiers for potential trial: pedigree/type, breeder's rights, climatic suitability, trial results, yield, water/salinity/heat tolerances, growth cycle, germination and genetic purity.
3) Applicable China-side seed export permits, phytosanitary certificate format, non-GMO testing and required IP/use restrictions for trials in Iran.
4) Whether your 25,000-kg MOQ applies strictly to commercial supply and whether permitted scientific trials have a separately approved arrangement.
5) A possible technical call between the breeding specialists for preliminary discussion, without exchange of restricted biological material or any procurement obligation.

We will obtain independent guidance on Iran's seed registration, quarantine and research import rules before any physical seeds move.

""" }
]
def safe_store(filename,obj):
    fd,temp=tempfile.mkstemp(prefix=".tmp-trade-",dir=str(filename.parent),text=True)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as out:
            os.chmod(temp,0o600)
            json.dump(obj,out,ensure_ascii=False,sort_keys=True,indent=2)
            out.flush();os.fsync(out.fileno())
        os.replace(temp,filename)
    finally:
        if os.path.exists(temp):os.unlink(temp)
def matching_reply(addr):
    result=[]
    for folder in ("new","cur"):
        p=MAILDIR/folder
        if not p.is_dir():continue
        for fn in p.iterdir():
            if not fn.is_file():continue
            try:
                stat=fn.stat()
                if stat.st_mtime<CUTOFF:continue
                if stat.st_size>22_000_000:continue
                with fn.open("rb") as f:
                    message=BytesParser(policy=policy.default).parse(f,headersonly=True)
                sender=parseaddr(str(message.get("From","")))[1].lower()
                if sender!=addr:continue
                if not (message.get("In-Reply-To") or message.get("References")
                        or "zomorod melal" in str(message.get("Subject","")).lower()):
                    continue
                result.append((stat.st_mtime,message))
            except (OSError,ValueError,UnicodeError):
                continue
    return max(result,key=lambda x:x[0])[1] if result else None
def build(target,original):
    msg=EmailMessage()
    original_subject=str(original.get("Subject","")).strip().replace("\r"," ").replace("\n"," ")
    if len(original_subject)>215:original_subject=original_subject[:215]
    msg["From"]=f"Zomorod Melal Trade Development <{SENDER}>"
    msg["To"]=target["address"]
    msg["Reply-To"]=SENDER
    msg["Date"]=email.utils.formatdate(localtime=False,usegmt=True)
    msg["Message-ID"]=email.utils.make_msgid(domain="zomorodmelal.ir")
    msg["Subject"]= original_subject if original_subject.lower().startswith(("re:","回复","re：")) else "Re: "+original_subject
    reference=str(original.get("Message-ID","")).strip()
    if re.fullmatch(r"<[^<>\r\n]{2,250}>",reference):
        msg["In-Reply-To"]=reference
        ref=str(original.get("References","")).strip()
        if ref and len(ref)<850 and "\r" not in ref and "\n" not in ref:
            msg["References"]=ref+" "+reference
        else:
            msg["References"]=reference
    msg.set_content(target["body"]+CLOSING,charset="utf-8")
    return msg
def main():
    os.umask(0o077)
    if not MAILDIR.is_dir():raise SystemExit("MAILDIR_NOT_AVAILABLE")
    if not Path("/usr/sbin/sendmail").is_file():raise SystemExit("EXIM_SENDMAIL_MISSING")
    mailbox=subprocess.run(["uapi","--output=json","Email","list_pops"],capture_output=True,text=True,check=True,timeout=30)
    res=json.loads(mailbox.stdout).get("result",{})
    addresses={str(x.get("email","")).lower() for x in res.get("data",[]) if isinstance(x,dict)}
    if res.get("status")!=1 or SENDER not in addresses:raise SystemExit("CORPORATE_FROM_NOT_VERIFIED")
    PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    PRIVATE.chmod(0o700)
    ledger=PRIVATE/(CAMPAIGN+".json")
    lock=PRIVATE/(CAMPAIGN+".lock")
    counters={"accepted":0,"already_attempted":0,"missing_inbound":0,"failed":0}
    with lock.open("a+") as lock_file:
        os.chmod(lock,0o600)
        fcntl.flock(lock_file,fcntl.LOCK_EX)
        state=json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {"campaign":CAMPAIGN,"entries":{}}
        print("CAMPAIGN=FIVE_INBOUND_SUPPLIER_SECOND_ROUND")
        print("REQUIRED_INBOUND_ORIGINAL=YES")
        print("NONBINDING_RFQ=YES")
        for idx,target in enumerate(TARGETS,1):
            key=target["key"]
            if key in state["entries"]:
                counters["already_attempted"]+=1
                print(f"FOLLOWUP_{idx:02d}=ALREADY_ATTEMPTED")
                continue
            inbound=matching_reply(target["address"])
            if inbound is None:
                counters["missing_inbound"]+=1
                print(f"FOLLOWUP_{idx:02d}=NO_MATCHING_INBOUND_REPLY")
                continue
            reply=build(target,inbound)
            state["entries"][key]={"status":"attempt_started","original_reference_sha256":hashlib.sha256(str(inbound.get("Message-ID","")).encode()).hexdigest()}
            safe_store(ledger,state)
            try:
                completed=subprocess.run(["/usr/sbin/sendmail","-t","-i","-f",SENDER],input=reply.as_bytes(),capture_output=True,timeout=55)
                good=completed.returncode==0
                state["entries"][key]["status"]="accepted_by_local_exim" if good else "submission_failed"
                state["entries"][key]["code"]=completed.returncode
                counters["accepted" if good else "failed"]+=1
                print(f"FOLLOWUP_{idx:02d}="+("ACCEPTED_BY_LOCAL_EXIM" if good else "SUBMISSION_FAILED"))
            except Exception as exc:
                state["entries"][key]["status"]="exception"
                state["entries"][key]["error_type"]=type(exc).__name__
                counters["failed"]+=1
                print(f"FOLLOWUP_{idx:02d}=EXCEPTION")
            safe_store(ledger,state)
    for name,num in counters.items():print(name.upper()+"="+str(num))
    if counters["failed"] or counters["missing_inbound"]:raise SystemExit(1)
if __name__=="__main__":
    main()
