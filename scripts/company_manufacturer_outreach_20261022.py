#!/usr/bin/env python3
"""One-time corporate procurement enquiries through the cPanel owner's local Exim.
Keeps private progress outside the website root. No orders or commitments."""
import email.utils
import fcntl
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from email.message import EmailMessage

CAMPAIGN = "cn-suppliers-catalogue-credit-20261022"
SENDER = "moj_1ro_1@zomorodmelal.ir"
REQUESTED_CREDIT = "180 to 250 days"
RECIPIENTS = [
    ("seed", "Hebei Shuangxing Seeds", "cherry@shuangxingseed.com"),
    ("seed", "China Vegetable Seed Co.", "zhongshuseeds@163.com"),
    ("seed", "Guangzhou Honghai Seed Industry", "hh.seeds@126.com"),
    ("seed", "Hefei Hefeng Seed", "hefengseed@163.com"),
    ("seed", "Shandong Jubao Yingrun Seed", "jubaolydia@163.com"),
    ("seed", "Known-You Seed (China)", "kycseed@knownyou.com.cn"),
    ("seed", "Tianjin Xian You Da Seed", "xianyoudaseed@163.com"),
    ("seed", "Sichuan Golden Ant Agricultural", "scjat2012@126.com"),
    ("seed", "Beijing Shengnong Agricultural Technology", "shengnong010@163.com"),
    ("seed", "Hubei Allwin Agriculture", "zhouyunpeng@hballwin.com"),
    ("crop_protection", "Jiangshan Agrochemical", "trade@jsac.com.cn"),
    ("crop_protection", "Hunan Bidechem", "info@bidechem.com.cn"),
    ("crop_protection", "Shanghai UPC", "sasha@shupc.com.cn"),
    ("crop_protection", "Nanjing Essence Fine-Chemical", "sales@essencechem.com"),
    ("crop_protection", "Zhejiang Rayfull", "sales@rayfull.com"),
    ("crop_protection", "Lianhetech Crop Protection", "BUAGRO@lianhetech.com"),
    ("fertilizer", "Shanxi Beacon Technology", "sales@aminoacids-agrochem.com"),
    ("fertilizer", "KingProlly Chemical", "Lily@king-boron.com"),
    ("fertilizer", "Hebei Monband Water Soluble Fertilizer", "info@monband.com"),
    ("fertilizer", "Ningbo MOS Chemical", "info@mos-agro.com"),
    ("fertilizer", "Nefi Agricultural Technology (Shandong)", "info@nefiedta.com"),
    ("fertilizer", "Chemland Group", "sales@chemlandgroup.com"),
    ("fertilizer", "Rensino Fertilizer Industrial", "info@china-fertilizers.com"),
    ("genetics", "Beijing Lianyu Cattle Breeding", "lianyurouniu@163.com"),
    ("genetics", "Shandong Guangming Biotechnology", "guangming@guangmingbio.com"),
    ("genetics", "Beijing Dafaun Poultry Breeding", "dafaun@dafaun.com"),
    ("ornamental", "Guangzhou Animal-X", "kevin@animal-x.cn"),
    ("veterinary", "Hebei Veyong Pharmaceutical", "info-vet@chinalimin.com"),
    ("veterinary", "Hebei Huabang Biotechnology", "china@huabangvet.com"),
    ("veterinary", "Sichuan Jinmao Biotechnology", "sales@jinmaoanimalhealth.com"),
    ("veterinary", "Shandong Unovet Pharmaceutical", "info@sdunovet.com"),
    ("veterinary", "Hebei Jinfeng Animal Pharmaceutical", "hebeijinfeng@gmail.com"),
    ("veterinary", "Hebei Lihua Pharmaceutical", "info@hb-lhyy.com"),
]
TOPICS = {
    "seed": (
        "hybrid and open-pollinated crop seeds, breeding varieties and seed supply",
        "Please include varieties, germination and purity test data, phytosanitary export documents, "
        "crop adaptation information, breeder rights and seed pack options by weight or seed count."
    ),
    "crop_protection": (
        "crop protection products and agricultural pesticide formulations",
        "Please include formulation strengths, active ingredients, safety data sheets (SDS), "
        "certificates of analysis, licensed manufacturing, efficacy data and applicable registration documents."
    ),
    "fertilizer": (
        "fertilizers, chelated micronutrients, foliar nutrition and crop biostimulants",
        "Please include nutrient composition, chelation/solubility, heavy-metal and quality analyses, "
        "technical sheets, shelf life and standard powder/liquid retail and bulk pack options."
    ),
    "genetics": (
        "cattle, sheep, goats and poultry breeding genetics and lawful genetic materials",
        "Please include breeds/lines, pedigree, performance records, veterinary and health certificates, "
        "traceability, export procedures and legal availability for Iran. For biological materials, "
        "original breeder identity and records must remain intact; co-branded distribution only where lawful."
    ),
    "ornamental": (
        "lawful ornamental bird breeding stock and aviculture cooperation",
        "Please include species/strains, breeder records, captive-bred origin, veterinary tests, quarantine "
        "arrangements, applicable CITES documents and legal export eligibility. "
        "Original species and breeding provenance must remain intact; co-branded materials only where lawful."
    ),
    "veterinary": (
        "veterinary pharmaceuticals, feed additives and animal nutrition supplements for cattle, sheep, goats and poultry",
        "Please include complete formulation and ingredient lists, GMP/quality certification, labels, "
        "safety information, withdrawal periods where relevant, stability/shelf-life, cold-chain needs "
        "and any Iranian registration or import requirements."
    ),
}
def compose(category, company, recipient):
    focus, technical = TOPICS[category]
    msg = EmailMessage()
    msg["From"] = f"Zomorod Melal International Cooperation <{SENDER}>"
    msg["To"] = recipient
    msg["Reply-To"] = SENDER
    msg["Subject"] = (
        f"Zomorod Melal & {company}: full product catalogue, OEM cooperation, 180-250 day credit"
    )
    msg["Date"] = email.utils.formatdate(localtime=False, usegmt=True)
    msg["Message-ID"] = email.utils.make_msgid(domain="zomorodmelal.ir")
    if category in ("genetics", "ornamental"):
        branding = (
            "We also welcome co-branded lawful distribution materials and appropriate market presentation. "
            "Authentic origin, animal identity, pedigree and health records must not be replaced or obscured."
        )
    else:
        branding = (
            "We would like OEM/contract-manufactured items packed under our Zomorod Melal brand, "
            "with compliant Persian/English labelling, manufacturer identity and origin, batch/lot and expiry "
            "information, and customary Iranian market retail and wholesale pack sizes chosen per item. "
            "Please confirm label artwork approval, minimum packaging quantities and pricing."
        )
    body = f"""Dear {company} Export / International Business Development Team,

I am writing on behalf of Zomorod Melal Agro-Industry Company, Iran, led by Chief Executive Officer Mojtaba Roozegar. We are considering a long-term supply and distribution partnership focused on {focus}.

1) Full manufactured product list: Please email your COMPLETE current list of products manufactured by your company, preferably as an Excel file and PDF catalogue, showing all models/SKUs, specifications, production capacity, available packaging, minimum order quantity, samples, lead times, EXW/FOB prices and export documentation. Please clearly distinguish your own factory products from goods traded for other manufacturers.

2) Technical verification: {technical} Kindly attach relevant licences, quality certificates and technical or regulatory data.

3) Our brand and market presentation: {branding}

4) Deferred credit: Please propose supplier trade credit of {REQUESTED_CREDIT} from the shipment-document date. If open-account terms are not feasible, please outline lawful alternatives such as insured export credit or a usance letter of credit and the requirements for qualification.

5) Iran partnership: Please describe lawful delivery options to Iran, export conditions, distributor/representation opportunities, support for import approvals, and your export sales manager's contact details. All supply and branding are subject to relevant Chinese and Iranian regulations.

This is an initial request for information and a non-binding proposal, not a purchase order or promise of payment. We look forward to receiving your complete manufactured-product catalogue and written commercial terms.

Kind regards,
International Cooperation Desk
For Mojtaba Roozegar, Chief Executive Officer
Zomorod Melal Agro-Industry Company
https://zomorodmelal.ir
Email: {SENDER}
"""
    msg.set_content(body)
    return msg

def save_state(path, state):
    fd, tmp = tempfile.mkstemp(prefix=".pending-", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            os.chmod(tmp, 0o600)
            json.dump(state, fh, ensure_ascii=False, sort_keys=True, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def main():
    os.umask(0o077)
    if len(RECIPIENTS) != 33 or len({x[2].lower() for x in RECIPIENTS}) != 33:
        raise SystemExit("RECIPIENT_PREFLIGHT_FAILED")
    categories = {key: sum(category == key for category, _, _ in RECIPIENTS) for key in TOPICS}
    if categories != {"seed": 10, "crop_protection": 6, "fertilizer": 7, "genetics": 3, "ornamental": 1, "veterinary": 6}:
        raise SystemExit("CATEGORY_PREFLIGHT_FAILED")
    for _, _, address in RECIPIENTS:
        if "@" not in address or "\n" in address or "\r" in address:
            raise SystemExit("ADDRESS_PREFLIGHT_FAILED")
    p = subprocess.run(["uapi", "--output=json", "Email", "list_pops"], capture_output=True, text=True, timeout=30, check=True)
    result = json.loads(p.stdout).get("result", {})
    if result.get("status") != 1:
        raise SystemExit("CPANEL_MAILBOX_LIST_FAILED")
    known = {str(row.get("email", "")).lower() for row in result.get("data", []) if isinstance(row, dict)}
    if SENDER not in known:
        raise SystemExit("CORPORATE_SENDER_NOT_OWNED_BY_CPANEL_ACCOUNT")
    if not pathlib.Path("/usr/sbin/sendmail").exists():
        raise SystemExit("EXIM_SENDMAIL_NOT_FOUND")
    root = pathlib.Path.home() / ".company-outreach-private"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    lock_path = root / (CAMPAIGN + ".lock")
    ledger = root / (CAMPAIGN + ".json")
    with lock_path.open("a+") as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        if ledger.exists():
            with ledger.open(encoding="utf-8") as fp:
                state = json.load(fp)
        else:
            state = {"campaign": CAMPAIGN, "sender": SENDER, "entries": {}}
        print("CAMPAIGN=" + CAMPAIGN, flush=True)
        print("EXPECTED_RECIPIENTS=" + str(len(RECIPIENTS)), flush=True)
        for idx, (category, company, recipient) in enumerate(RECIPIENTS, 1):
            key = recipient.casefold()
            if key in state["entries"]:
                print(f"RECIPIENT_{idx:02d}={category}:ALREADY_ATTEMPTED", flush=True)
                continue
            msg = compose(category, company, recipient)
            state["entries"][key] = {
                "category": category, "company": company,
                "status": "attempt_started",
                "message_id": str(msg["Message-ID"]),
                "time_utc": email.utils.formatdate(localtime=False, usegmt=True),
            }
            save_state(ledger, state)
            try:
                sent = subprocess.run(
                    ["/usr/sbin/sendmail", "-t", "-i", "-f", SENDER],
                    input=msg.as_bytes(), capture_output=True, timeout=35
                )
                state["entries"][key]["status"] = "accepted_by_local_exim" if sent.returncode == 0 else "mail_submission_failed"
                state["entries"][key]["exit_code"] = sent.returncode
            except Exception as exc:
                state["entries"][key]["status"] = "submission_exception"
                state["entries"][key]["error_type"] = type(exc).__name__
            save_state(ledger, state)
            print(f"RECIPIENT_{idx:02d}={category}:{state['entries'][key]['status']}", flush=True)
            if idx < len(RECIPIENTS):
                time.sleep(8)
        by_status = {}
        for item in state["entries"].values():
            by_status[item["status"]] = by_status.get(item["status"], 0) + 1
        print("SUBMITTED_TO_EXIM=" + str(by_status.get("accepted_by_local_exim", 0)), flush=True)
        print("UNCONFIRMED_OR_FAILED=" + str(sum(n for status, n in by_status.items() if status != "accepted_by_local_exim")), flush=True)
        print("REMOTE_DELIVERY_NOT_YET_VERIFIED", flush=True)
        if by_status.get("accepted_by_local_exim", 0) < 30:
            raise SystemExit(2)

if __name__ == "__main__":
    main()
