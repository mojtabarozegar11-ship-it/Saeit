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

CAMPAIGN = "ru-suppliers-catalogue-credit-20261022"
SENDER = "moj_1ro_1@zomorodmelal.ir"
REQUESTED_CREDIT = "180 to 250 days"
RECIPIENTS = [
    ("seed", "Gavrish", "gavrish@gavrish.ru"),
    ("seed", "Agrofirm POISK", "info@semenasad.ru"),
    ("seed", "SeDeK", "shop@sedek.ru"),
    ("seed", "Aelita", "zakaz@ailita.ru"),
    ("seed", "Agroplazma", "zelensky.p@agroplazma.com"),
    ("seed", "RUSEED", "info@ruseed.ru"),
    ("seed", "SEMKO", "opt@semco.ru"),
    ("seed", "Manul", "info@manul.ru"),
    ("seed", "Sortsemovosh", "torg@seed.ru"),
    ("crop_protection", "Avgust", "corporate@avgust.com"),
    ("crop_protection", "Shchelkovo Agrohim", "info@betaren.ru"),
    ("crop_protection", "Lysterra", "tverskih@lysterra.ru"),
    ("crop_protection", "Soyuzagrohim", "info@s-ah.ru"),
    ("crop_protection", "Agro Expert Group", "info@agroex.ru"),
    ("fertilizer", "Buysky Chemical Plant", "info@bhz.ru"),
    ("fertilizer", "Uralchem", "domestic@uralchem.com"),
    ("fertilizer", "PhosAgro", "centralasia@phosagro.ru"),
    ("fertilizer", "Acron", "info@acron.ru"),
    ("fertilizer", "BioMaster", "zakaz@biomaster.pro"),
    ("fertilizer", "BashInkom", "bashinkom@mail.ru"),
    ("genetics", "Moskovskoe Breeding Enterprise", "plemotdel@mos-bulls.ru"),
    ("genetics", "Genoservis Rusko", "info@genoservisrusko.com"),
    ("genetics", "Genetic Reproduction Center GCV", "plem@oaohcr.ru"),
    ("ornamental", "Genofond Sergiev Posad", "a89260194451@rambler.ru"),
    ("veterinary", "NITA-FARM", "client@nita-farm.ru"),
    ("veterinary", "Apicenna", "info@apicenna.ru"),
    ("veterinary", "VIC Group", "info@vicgroup.ru"),
    ("veterinary", "Bionit", "sale@bionit.ru"),
    ("veterinary", "Agrobioprom", "preparati@agrobioprom.ru"),
    ("veterinary", "Agrovetzashchita AVZ", "admin@vetmag.ru"),
    ("feed", "MEGAMIX", "info@megamix.ru"),
]
TOPICS = {
    "seed": ("семена овощных, зерновых, кормовых и других сельхозкультур, сорта и гибриды",
             "Всхожесть, сортовая чистота, протоколы испытаний, фитосанитарные сертификаты, права селекционеров, фасовка по массе и количеству семян."),
    "crop_protection": ("средства защиты растений, гербициды, инсектициды, фунгициды и биопрепараты",
             "Состав и концентрации действующих веществ, регистрационные документы, паспорта безопасности, сертификаты анализа, сроки годности и упаковка."),
    "fertilizer": ("минеральные, водорастворимые и листовые удобрения, микроэлементы и хелатные комплексы",
             "Содержание элементов питания, растворимость, хелатирование, анализ тяжелых металлов, протоколы качества, фасовка и срок хранения."),
    "genetics": ("племенная генетика КРС, овец, коз и птицы, племенной материал и программы селекции",
             "Породы и линии, родословные, индекс племенной ценности, ветеринарные сертификаты, прослеживаемость, законность экспорта и карантин."),
    "ornamental": ("коллекционные и декоративные породы птицы, инкубационные яйца и законный племенной материал",
             "Перечень пород и видов, происхождение от разводимых в неволе птиц, ветеринарные проверки, карантин, CITES при необходимости и законный экспорт."),
    "veterinary": ("ветеринарные препараты, кормовые добавки, витамины и добавки для КРС, овец, коз и сельскохозяйственной птицы",
             "Полные составы, GMP и лицензии, инструкции, противопоказания, сроки ожидания, условия хранения, холодовая цепь и регистрационные документы."),
    "feed": ("комбикорма, премиксы, белково-витаминно-минеральные концентраты и кормовые добавки для КРС, овец, коз и птицы",
             "Составы и гарантированные показатели питательности, контроль загрязнителей, срок хранения, безопасность кормов и заводская фасовка."),
}

def compose(category, company, recipient):
    focus, technical = TOPICS[category]
    msg = EmailMessage()
    msg["From"] = f"Zomorod Melal International Cooperation <{SENDER}>"
    msg["To"] = recipient
    msg["Reply-To"] = SENDER
    msg["Subject"] = f"Земруд Меллал — {company}: полный каталог, СТМ / OEM и отсрочка 180–250 дней"
    msg["Date"] = email.utils.formatdate(localtime=False, usegmt=True)
    msg["Message-ID"] = email.utils.make_msgid(domain="zomorodmelal.ir")
    if category in ("genetics", "ornamental"):
        branding = (
            "Просим рассмотреть законное совместное продвижение и ко-брендинг под маркой Zomorod Melal. "
            "Исходные сведения о породе, селекционере, происхождении, идентичности и здоровье животных должны полностью сохраняться. "
            "Переупаковка биоматериалов без соответствующих разрешений не предлагается."
        )
    else:
        branding = (
            "Рассматриваем контрактное производство / СТМ (OEM/private label) под нашим брендом Zomorod Melal "
            "с упаковкой в распространенных на рынке Ирана розничных и оптовых объемах по каждой позиции. "
            "Этикетка на персидском и английском языках должна законно указывать реального изготовителя, страну происхождения, "
            "состав, партию, даты изготовления и годности. Сообщите минимальный тираж, стоимость упаковки и согласование макета. "
            "Если перефасовка или СТМ для определенных позиций запрещена, предложите официальную дистрибуцию с сохранением марки изготовителя."
        )
    letter = f"""Уважаемые коллеги компании {company}!

От имени иранской компании Zomorod Melal Agro-Industry (Кешт ва Санат Земруд Меллал), генеральный директор Mojtaba Roozegar (Моджтаба Рузегар), предлагаем обсудить долгосрочное сотрудничество по направлению: {focus}.

1. ПОЛНЫЙ КАТАЛОГ ПРОИЗВОДСТВА. Просим прислать ПОЛНЫЙ актуальный перечень выпускаемой именно вашим предприятием продукции (по возможности Excel и PDF): названия и коды всех SKU, характеристики, мощность, фасовку, минимальный заказ (MOQ), стоимость образцов, сроки изготовления, экспортные цены EXW/FCA/FOB и условия отгрузки. Отдельно отметьте товары сторонних заводов, если они есть.

2. ТЕХНИЧЕСКИЕ И РАЗРЕШИТЕЛЬНЫЕ ДОКУМЕНТЫ. {technical} Приложите доступные сертификаты качества, лицензии изготовителя, протоколы и документы, необходимые для законного импорта в Иран.

3. УПАКОВКА ПОД НАШИМ БРЕНДОМ. {branding}

4. ТОВАРНЫЙ КРЕДИТ. Рассмотрите отсрочку платежа на 180–250 календарных дней от даты отгрузочного документа. Если открытый товарный кредит недоступен, укажите законные варианты: страхование экспортного кредита, аккредитив с отсрочкой (usance LC), банковская гарантия и требования к кредитной оценке покупателя.

5. СОТРУДНИЧЕСТВО И ДОСТАВКА. Укажите, возможен ли экспорт в Иран с соблюдением действующих норм и ограничений, условия перевозки и таможенного оформления, возможности эксклюзивной дистрибуции, поддержки регистрации, контакт ответственного руководителя экспортного отдела и ориентировочные сроки ответа.

Это предварительный запрос информации, не заказ на закупку и не обязательство оплаты. Будем признательны за полный заводской каталог, проект коммерческих условий и прямой ответ на эту почту.

С уважением,
Отдел международного сотрудничества
По поручению Mojtaba Roozegar, генерального директора
Zomorod Melal Agro-Industry Company, Iran
https://zomorodmelal.ir
Электронная почта: {SENDER}

English summary: We request your COMPLETE manufacturer product catalogue, lawful OEM/private-label packing for Zomorod Melal where permitted, and a non-binding quotation including proposed 180–250 days supplier credit, shipping/export to Iran and compliance documents.
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
    if len(RECIPIENTS) != 31 or len({x[2].lower() for x in RECIPIENTS}) != 31:
        raise SystemExit("RECIPIENT_PREFLIGHT_FAILED")
    categories = {key: sum(category == key for category, _, _ in RECIPIENTS) for key in TOPICS}
    if categories != {"seed": 9, "crop_protection": 5, "fertilizer": 6, "genetics": 3, "ornamental": 1, "veterinary": 6, "feed": 1}:
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
        if by_status.get("accepted_by_local_exim", 0) < 31:
            raise SystemExit(2)

if __name__ == "__main__":
    main()
