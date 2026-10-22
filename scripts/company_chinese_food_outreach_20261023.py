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

CAMPAIGN = "cn-food-manufacturers-catalogue-credit-20261023"
SENDER = "moj_1ro_1@zomorodmelal.ir"
REQUESTED_CREDIT = "180 to 250 days"
RECIPIENTS = [
    [
        "sweeteners",
        "KETONG GROUP",
        "sales@kt95.cn",
        "https://www.kt95.cn/"
    ],
    [
        "sweeteners",
        "Shandong Huaxian Haosen Biotech",
        "molly@steviachina.com",
        "https://www.steviachina.com/"
    ],
    [
        "sweeteners",
        "Hangzhou Health Sweet Biotech",
        "info@health-sweet.com",
        "https://www.health-sweet.com/"
    ],
    [
        "sweeteners",
        "Techno Fujian Food Ingredients",
        "sales@techno-fi.com",
        "https://www.techno-fi.com/"
    ],
    [
        "sweeteners",
        "HOWTIAN Group",
        "info@howtiangroup.com",
        "https://www.howtiangroup.com/"
    ],
    [
        "sweeteners",
        "Hebei Tubang Biotechnology",
        "sales@tbbiotech.com",
        "https://www.tbbiotech.com/"
    ],
    [
        "sweeteners",
        "China Functional Sugar",
        "bill@sumsupply.com",
        "https://www.functionsugar.com/"
    ],
    [
        "ingredients",
        "FOODCHEM International Corporation",
        "sales@foodchem.cn",
        "https://www.foodchem.cn/pages/Contact/"
    ],
    [
        "ingredients",
        "Rensino Food Additives",
        "export@china-food-additives.com",
        "https://www.china-food-additives.com/"
    ],
    [
        "ingredients",
        "Hangzhou Union Biotechnology",
        "info@chinafoodchem.com",
        "https://www.chinafoodchem.com/"
    ],
    [
        "ingredients",
        "RZBC Group",
        "rzbc@rzbc.com",
        "https://en.rzbc.com/"
    ],
    [
        "ingredients",
        "China Lecithin ZC",
        "sales@chinalecithin.com",
        "https://www.chinalecithin.com/"
    ],
    [
        "ingredients",
        "Hugestone Enterprise",
        "sales2@hugestone-china.com",
        "https://www.hugestoneingredient.com/"
    ],
    [
        "plant_extracts",
        "Shanghai Kayson Flavor Fragrance",
        "sales@chinafoodflavors.com",
        "https://www.chinafoodflavors.com/"
    ],
    [
        "plant_extracts",
        "CNGreatFlavor",
        "sales@cngreatflavor.com",
        "https://www.cngreatflavor.com/"
    ],
    [
        "plant_extracts",
        "New Natural Biotechnology",
        "sales@chinaherbextract.com",
        "https://www.chinaherbextract.com/"
    ],
    [
        "plant_extracts",
        "Chengdu CHY Konjac Gum",
        "amandazhuo@chykonjacgum.com",
        "https://www.chykonjacgum.com/"
    ],
    [
        "plant_extracts",
        "HKAY Biotechnology",
        "agar@agar.cn",
        "https://agargum.com/"
    ],
    [
        "plant_extracts",
        "Dangshan Haisheng Pectin",
        "hui.zhang@dshaisheng.com",
        "https://dshaisheng.com/en/"
    ],
    [
        "starch_protein",
        "Taichy Supply",
        "info@taichysupply.com",
        "https://www.taichysupply.com/"
    ],
    [
        "starch_protein",
        "Tianjiang Modified Starch",
        "sales@tianjiangmodifiedstarch.com",
        "https://www.tianjiangmodifiedstarch.com/"
    ],
    [
        "starch_protein",
        "Shandong Huatai Food Products",
        "peaprotein80@163.com",
        "https://www.huataiprotein.com/contact.html"
    ],
    [
        "starch_protein",
        "Xingmao Corn Processing",
        "export@xingmao.cn",
        "https://en.xingmao.cn/"
    ],
    [
        "starch_protein",
        "Shengtaigroup",
        "sales01@shengtaigroup.net",
        "https://www.shengtaigroup.net/"
    ],
    [
        "starch_protein",
        "Shandong Yuwang Ecological Food",
        "yuwangeco@yuwangcn.com",
        "https://en.yuwangprotein.com/"
    ],
    [
        "processed_veg",
        "Handan Green Healthy Dehydrated Vegetables",
        "food@lverkang.cn",
        "https://www.lverkang.cn/"
    ],
    [
        "processed_veg",
        "Xuzhou Lujian Dehydrated Vegetables",
        "daisygu@xzlujian.com",
        "https://www.dryvegetable.com/en/index.jsp"
    ],
    [
        "processed_veg",
        "Jiangsu Lvwei Food Technology",
        "lvweifoods@163.com",
        "https://lvweifood.com/"
    ],
    [
        "processed_veg",
        "Shandong Sanxing Food",
        "info@sanxingfood.com",
        "https://www.sanxingfood.com/"
    ],
    [
        "processed_veg",
        "Trans-High Food",
        "info@trans-high.com",
        "https://www.trans-high.com/"
    ],
    [
        "processed_veg",
        "Zhangzhou Jindefu Foods IQF",
        "owenzheng@jindefufood.com",
        "https://www.jindefufood.com/"
    ],
    [
        "processed_veg",
        "Shenzhen Channel Run Juice",
        "sara@channeljuice.com",
        "https://www.channeljuice.com/contact.html"
    ],
    [
        "processed_veg",
        "Freshco Industry Fruit Juice",
        "lbfruit@126.com",
        "https://www.freshcojuice.cn/"
    ],
    [
        "prepared_food",
        "Tomato Brothers Enterprise",
        "wang@tomatobr.cn",
        "https://chinatomatopaste.cn/contact-us/"
    ],
    [
        "prepared_food",
        "Tianjin Tianwei Food",
        "michelle@tjtwfood.com",
        "https://www.china-tomato.com/contact.html"
    ],
    [
        "prepared_food",
        "Tianjin Bliss Food",
        "cindy@blisstomato.com",
        "https://blisstomato.com/contact/"
    ],
    [
        "prepared_food",
        "AHCOF Neochains Food Technology",
        "sales@zasavor.com",
        "https://www.zasavorpure.com/contact-us"
    ],
    [
        "prepared_food",
        "Foshan Guanggu Seasoning",
        "postmaster@ggfcs.com",
        "https://www.ggfcs.com/contactus.html"
    ],
    [
        "prepared_food",
        "Zhangzhou Chengmou Food",
        "sales@chengmoufood.com",
        "https://chengmoufood.com/"
    ],
    [
        "prepared_food",
        "Noodle House Food",
        "henrysu@noodlehousefood.com",
        "https://www.noodlehousefood.com/"
    ],
    [
        "prepared_food",
        "Qingdao Sinomie Food",
        "sales@sinomie.com.cn",
        "https://www.sinomie-noodles.com/"
    ],
    [
        "prepared_food",
        "Tianz Tealeaf",
        "export@china-tealeaf.com",
        "https://www.china-tealeaf.com/"
    ],
    [
        "prepared_food",
        "Linklife Food",
        "export@linklifegroup.com",
        "https://www.linklifegroup.com/"
    ],
    [
        "prepared_food",
        "Anhui Yangfujin Condiment",
        "office@yangfuijn.cn",
        "https://www.yfjseasoning.com/about-us"
    ],
    [
        "fermentation",
        "Grand Life Sciences Food Probiotics",
        "liuyanmei@cgelsg.com",
        "https://www.cgeprobiotics.com/contact-us"
    ],
    [
        "fermentation",
        "Tessin Biotechnology",
        "jenny@tessinlife.com",
        "https://www.tessinglucan.com/contact-us"
    ],
    [
        "fermentation",
        "Tangshan Top Biotechnology",
        "topyeast-1998@foxmail.com",
        "https://www.nutritionyeast.com/inquiry"
    ],
    [
        "fermentation",
        "Heilongjiang Jiuding Yeast",
        "jiudingyeast@vip.163.com",
        "https://www.jiudingyeast.com/en/index.php?lanmu=9&p=about"
    ],
    [
        "fermentation",
        "Sunson Industry Group Enzymes",
        "business@sunsonzymes.com",
        "https://www.sunsonenzyme.com/Customer_Centre/Partner/"
    ],
    [
        "fermentation",
        "Chibio Biotech",
        "sales@chibiotech.com",
        "https://www.chibiotech.com/product/amylase/"
    ]
]
TOPICS = {
    "sweeteners": [
        "stevia extracts, sugar alternatives and food-grade sweeteners",
        "Sweetness and purity profile, food-grade standards, allowable uses, maximum use rates, analytical CoA, heavy metals, microbiology and GMO status."
    ],
    "ingredients": [
        "food-grade acidulants, preservatives, stabilisers, lecithin and other legally permitted additives",
        "Exact chemical identity and INS/E-number where applicable, regulatory food-grade status, full composition, allergen declaration, batch CoA, traceability and approved applications."
    ],
    "plant_extracts": [
        "food-grade natural flavors, fruit or botanical extracts, konjac, pectin, agar and plant-based gelling ingredients",
        "Botanical species and source, solvent/carrier declaration, no ethanol or other non-halal carriers, extraction method, allergen/cross-contact control and batch CoA."
    ],
    "starch_protein": [
        "edible starches, dextrins, glucose, maltodextrin, plant proteins and functional food ingredients",
        "Food-grade specification, DE/viscosity/protein percentages as applicable, GMO and allergen declarations, heavy-metal and microbiological tests, country of origin and traceability."
    ],
    "processed_veg": [
        "dehydrated vegetables, IQF vegetables and fruits, fruit juice concentrates and processed agricultural foods",
        "Agricultural origin, pesticide residue testing, Brix and additives when applicable, microbiology, cold-chain or storage requirements, usable shelf life and plant-level traceability."
    ],
    "prepared_food": [
        "tomato paste, sauces and condiments, canned foods, noodles, tea and other shelf-stable packaged foods",
        "Full recipe/ingredient disclosure, sodium/sugar information, allergens, permissible additives, shelf life, retail and catering packaging, relevant sterilization or processing specifications."
    ],
    "fermentation": [
        "edible yeast, probiotics and enzymes manufactured for food and beverage processing",
        "Strain identity and viability where relevant, enzyme activity and specific uses, food-grade safety data, batch testing, storage conditions, allergen and GMO status."
    ]
}

def compose(category, company, recipient):
    focus, technical = TOPICS[category]
    msg = EmailMessage()
    msg["From"] = f"Zomorod Melal International Cooperation <{SENDER}>"
    msg["To"] = recipient
    msg["Reply-To"] = SENDER
    msg["Subject"] = f"Zomorod Melal & {company} | Full food products catalog, OEM, 180-250 day credit"
    msg["Date"] = email.utils.formatdate(localtime=False, usegmt=True)
    msg["Message-ID"] = email.utils.make_msgid(domain="zomorodmelal.ir")
    letter = f"""Dear {company} Export Sales Team,

We are writing on behalf of Zomorod Melal Agro-Industry Company, Iran, led by CEO Mojtaba Roozegar. We are exploring a long-term, lawful supply and distribution partnership for the Iranian market in your area of specialization: {focus}.

1. COMPLETE MANUFACTURED PRODUCTS LIST
Please send your CURRENT COMPLETE FACTORY PRODUCT CATALOGUE (PDF and ideally editable Excel), including every relevant SKU/product code, specifications, available grades and options, production capacity, MOQ, sample cost, typical lead time and bulk export quotations EXW/FOB/FCA. Clearly distinguish products made at your own licensed factory from third-party sourced or traded items, and name the actual manufacturer.

2. FOOD SAFETY, TRACEABILITY AND MARKET ELIGIBILITY
Please include your genuine factory business/food-production licenses, applicable HACCP / ISO 22000 / FSSC 22000 / BRCGS certificates, Halal certificates where relevant, recent product-specific certificates of analysis (CoA), ingredients and allergen declarations, country of origin, lot-level traceability, storage/shelf life, and export/registration documents required for lawful import into Iran. Priority technical points: {technical}
We seek only products suitable for the Iranian food market: NO pork, porcine gelatin or any pig-derived ingredient, and no non-halal ingredients or alcoholic food preparations. Please flag any products or flavor carriers that do not meet these restrictions instead of including them as offers.

3. ZOMOROD MELAL OEM / PRIVATE-LABEL PACKAGING
Please specify whether you can supply genuine contract-manufactured products under our "Zomorod Melal" brand in common, commercially practical Iranian market sizes (consumer packs where appropriate, food-service packs and 10/20/25 kg industrial bags as appropriate). Request a separate MOQ, artwork/printing setup cost, available packaging options and lead time for each product family. All labels must legally disclose the true producer, origin, full ingredients, allergens, batch, production/expiry dates and other required information in Persian and English. If private labeling is not legally available, kindly offer authorized distribution with original brand preserved.

4. DEFERRED PAYMENT / EXPORT FINANCE
Would you consider 180-250 CALENDAR DAYS of supplier credit from the shipment-document date, subject to your credit approval? This is a requested commercial term, NOT an already agreed facility. If open-account credit is unavailable, please propose any lawful insured export credit, usance letter of credit, bank guarantee or other compliant trade-finance structure, identifying prerequisites, bank availability and fees.

5. LAWFUL IRAN MARKET EXPORT / FOLLOW-UP
Please confirm whether your company can legally sell and ship these goods to Iran with full compliance with applicable regulations and export-control restrictions. Provide shipping terms, export documentation, private-label support, whether exclusivity is possible, a named export-sales contact, and when your complete catalogue and quotation will be available.

This is solely a NON-BINDING request for information and quotation. No purchase order, payment obligation, exclusivity, legal agency or guaranteed future volume is created by this email. Please reply directly with the FULL manufactured product catalogue and suggested next steps.

Kind regards,
International Cooperation Office
On behalf of Mojtaba Roozegar, Chief Executive Officer
Zomorod Melal Agro-Industry Company, Iran
https://zomorodmelal.ir
Email: {SENDER}

中文摘要：我司为伊朗 Zomorod Melal 农工公司。请提供贵司自产食品及食品原料的完整产品目录、出厂规格、出口报价、MOQ、食品安全及清真资料，并说明能否依法出口伊朗、提供自有品牌 OEM 包装，以及是否可考虑经信用审核后 180–250 天账期。本邮件仅为询价，不构成订单或付款承诺。
"""
    msg.set_content(letter, charset="utf-8")
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
    if len(RECIPIENTS) != 50 or len({x[2].lower() for x in RECIPIENTS}) != 50 or len({x[1].casefold() for x in RECIPIENTS}) != 50:
        raise SystemExit("RECIPIENT_PREFLIGHT_FAILED")
    categories = {key: sum(category == key for category, _, _, _ in RECIPIENTS) for key in TOPICS}
    if categories != {"sweeteners":7,"ingredients":6,"plant_extracts":6,"starch_protein":6,"processed_veg":8,"prepared_food":11,"fermentation":6}:
        raise SystemExit("CATEGORY_PREFLIGHT_FAILED")
    for _, _, address, source in RECIPIENTS:
        if "@" not in address or "\n" in address or "\r" in address or not source.startswith("https://"):
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
        for idx, (category, company, recipient, source) in enumerate(RECIPIENTS, 1):
            key = recipient.casefold()
            if key in state["entries"]:
                print(f"RECIPIENT_{idx:02d}={category}:ALREADY_ATTEMPTED", flush=True)
                continue
            msg = compose(category, company, recipient)
            state["entries"][key] = {
                "category": category, "company": company, "official_contact_source": source,
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
        if by_status.get("accepted_by_local_exim", 0) < 50:
            raise SystemExit(2)

if __name__ == "__main__":
    main()
