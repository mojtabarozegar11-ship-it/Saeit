"""Deterministic, locally runnable research helpers. No LLM, network, or new claims.

Outputs are NOT research findings and must never be auto-published.
This module is also independently testable without Django.
"""
import hashlib
import re
from .generator import valid_sources

MAX_ARTICLE_BODY_CHARS = 100_000
MAX_SUMMARY_CHARS = 10_000
MAX_REFERENCE_LINKS = 30

KINDS = (
    ('research_digest', 'مرور منابع پژوهشی'),
    ('product_blueprint', 'طرح اولیه محصول پژوهشی'),
)
ENGINE_VERSION = '9.1'
DISCLAIMER = (
    'پیش‌نویس تولیدشده با قواعد نرم‌افزاری و صرفاً از متن منبع؛ '
    'فاقد اعتبار پژوهشی مستقل. پیش از انتشار باید منابع، حقوق نشر و تفسیر علمی بررسی شوند.'
)
class AgentInputError(ValueError):
    pass

def content_fingerprint(title, summary, body, sources, language):
    """Keep editions isolated and retries idempotent. No Python hash()."""
    payload='\x1f'.join([ENGINE_VERSION, title, summary, body, language, *sorted(valid_sources(sources))])
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def clean_text(raw):
    if not isinstance(raw, str):
        raise AgentInputError('invalid_text')
    # Do not transform Markdown to HTML; outputs render escaped by default.
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]{0,200}>', ' ', raw)).strip()

def build_output(kind, title, summary, body, sources, language='fa'):
    """Produces a digest or *proposal* from an existing, approved article.

    This is template-based extraction, not an AI diagnosis or real product.
    """
    if language != 'fa':
        raise AgentInputError('fa_only_until_translations_reviewed')
    if kind not in dict(KINDS):
        raise AgentInputError('unknown_agent')
    # Bound the workload before any expensive normalization or summarization.
    # Rejected inputs remain private and the worker records a controlled error.
    if (not isinstance(body,str) or len(body)>MAX_ARTICLE_BODY_CHARS or
        not isinstance(summary,str) or len(summary)>MAX_SUMMARY_CHARS or
        not isinstance(title,str) or len(title)>500 or
        not isinstance(sources,(list,tuple)) or len(sources)>MAX_REFERENCE_LINKS):
        raise AgentInputError('source_size_out_of_policy')
    name = clean_text(title)[:180]
    intro = clean_text(summary)
    text = clean_text(body)
    refs = valid_sources(sources)
    if len(name)<5 or len(intro)<35 or len(text)<250 or not refs:
        raise AgentInputError('approved_source_incomplete')
    # Extract only the author's existing words, not synthetic scientific facts.
    sections = [x.strip() for x in re.split(r'(?<=[.!؟؛])\s+',text) if len(x.strip())>=35]
    if not sections:
        sections = [text[:700]]
    excerpts=[]
    for part in sections:
        if len(excerpts)>=5:break
        if part not in excerpts:excerpts.append(part[:450])
    quote='\n\n'.join('• '+x for x in excerpts)
    links='\n'.join('• '+r for r in refs)
    if kind=='research_digest':
        heading=f'مرور پژوهشی: {name}'[:200]
        result=(f'مرور مقدماتی بر پایه مطلب منتشرشده «{name}»\n\n'
                f'خلاصه متن مرجع: {intro[:480]}\n\n'
                f'گزیده‌های قابل راستی‌آزمایی از منبع اصلی:\n{quote}\n\n'
                f'منابع درج‌شده در مطلب مرجع (اعتبار مستقل آن‌ها هنوز بررسی نشده):\n{links}\n\n'
                f'محدودیت و تکلیف سردبیری: {DISCLAIMER}')
    else:
        heading=f'طرح محصول پژوهشی: {name}'[:200]
        result=(f'طرح اولیه، نه محصول ساخته‌شده یا قابل فروش\n\n'
                f'موضوع مستند: {name}\n\n'
                f'شناخت اولیه مسئله از متن مرجع: {intro[:480]}\n\n'
                f'داده‌های موجود برای تعریف محدوده کار:\n{quote}\n\n'
                'خروجی پیشنهادی برای بررسی: دفترچه راهنما، چک‌لیست اعتبارسنجی، ابزار محاسبه آموزشی '
                'یا پرونده پژوهشی؛ انتخاب نهایی نیازمند تشخیص متخصص است.\n\n'
                'پیش‌نیاز تولید: تعیین مخاطب، پروتکل علمی، حقوق محتوا، مستندات، آزمون، '
                'قیمت‌گذاری و تأیید انسانی. درآمد و بازار تضمین‌شده نیست.\n\n'
                f'منابع مرجع:\n{links}\n\n'
                f'محدودیت: {DISCLAIMER}')
    result += ('\n\nمهر انتشاراتی پس از تأیید: مجتبی روزگار — محقق و پژوهشگر — '
               'مدیرعامل شرکت کشت و صنعت زمرد ملل. تنظیم ماشینی این متن، تألیف شخصی او محسوب نمی‌شود.')
    return {'title':heading,'summary':f'پیش‌نویس غیرقابل انتشار خودکار، برگرفته از: {name}'[:650],
            'body':result,'sources':refs,'provenance':'published_site_article',
            'engine_version':ENGINE_VERSION}
