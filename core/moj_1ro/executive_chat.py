"""Concise owner-facing results grounded in current executable receipts."""
NAMES={'finance_commerce':'بخش مالی و تجارت الکترونیک','income_research':'پژوهش درآمد','self_improvement':'ارتقای ربات و پروژه','economics':'اقتصاد','business':'کسب‌وکار','site':'سایت و برنامه‌نویسی',
       'trading':'معامله‌گری','games':'بازی‌سازی'}
STATES={'untested':'آزمایش نشده','observed':'بررسی انجام شده',
        'calculated':'محاسبه انجام شده','applied':'تغییر اعمال شده','blocked':'مانع اجرایی دارد'}

def format_result(capability,result):
    if capability=='executive.submit':
        if result.get('state') in ('ready','retry','running'):
            return 'مأموریت ثبت شد و در صف اجراست؛ نتیجه پس از اجرا مشخص می‌شود.'
        return 'وضعیت مأموریت ثبت‌شده: '+STATES.get(result.get('state'),str(result.get('state')))
    p=result.get('portfolio') or {}
    domains=p.get('domains') or {}
    rows=[NAMES[d]+': '+STATES.get(x.get('evidence_status'),'آزمایش نشده')
          for d,x in domains.items() if d in NAMES]
    return '؛ '.join(rows)+'.\nمعامله‌گری زنده، ساخت بازی و برنامه‌نویسی خودکار عمومی هنوز اثبات نشده‌اند.'
