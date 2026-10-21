# راهنمای بهره‌برداری خصوصی از سامانه امضا و داوری متخصصان — نسخه ۱

**وضعیت کنونی:** برنامه در VPS نصب شده است؛ هیچ فرد واقعی از طرف کارخانه تأیید نشده، هیچ کلید خصوصی متخصصی روی سرور تولید نشده و هیچ محصولی با این نصب گواهی کیفیت ۱۰۰۰/۱۰۰۰ نگرفته است.

## محل نصب

- مسیر سرور: `/home/githubops/factory-runtime/private/autonomous-product-cycle/quality-reviewer-console`
- فایل اجرا: `factory_quality_reviewer_console_v1.py`
- فایل تأیید امضا: `factory_quality_signed_approval_v1.py`
- نصب فقط در فضای خصوصی، با مجوزهای فایل محدود. این نسخه **پرتال عمومی وب یا سامانه ارسال ایمیل نیست**.
- نتیجه اجرای واقعی: GitHub Actions `39537615304`؛ ۱۶ تست موفق.

## ۱. مشاهده وضعیت واقعی

از حساب SSH مجاز `githubops`:

```bash
WORK="$HOME/factory-runtime/private/autonomous-product-cycle/quality-reviewer-console"
python3 -B "$WORK/factory_quality_reviewer_console_v1.py" status --workspace "$WORK"
```

تا وقتی متخصص واقعی ثبت نشده، `trusted_reviewer_count=0` صحیح است.

## ۲. دعوت متخصص واقعی

در محیط خصوصی سرور، پس از تعیین شناسه توسط مدیر مجاز:

```bash
python3 -B "$WORK/factory_quality_reviewer_console_v1.py" invite \
  --workspace "$WORK" \
  --reviewer-id independent_expert_001 \
  --role domain_specialist
```

شناسه فوق صرفاً **مثال** است و هویت واقعی شخص را اثبات نمی‌کند. سه نقش دیگر `independent_quality_auditor`، `rights_reviewer` و `owner` هستند. دعوت‌نامه را فقط از یک مجرای مطمئن به شخص حقیقی منتقل کنید.

## ۳. اثبات کلید توسط شخص حقیقی، روی دستگاه خودش

شخص، روی دستگاه امن **خودش** این کلید را تولید می‌کند (نه روی VPS، نه در GitHub):

```bash
openssl genpkey -algorithm Ed25519 -out my-private-signing-key.pem
chmod 600 my-private-signing-key.pem
openssl pkey -in my-private-signing-key.pem -pubout -out my-public-signing-key.pem
python3 factory_quality_reviewer_console_v1.py respond \
  --invitation my-invite.json \
  --private-key my-private-signing-key.pem \
  --public-key my-public-signing-key.pem \
  --output my-key-proof.json
```

**کلید خصوصی نباید در پیام، فایل ارسالی، مخزن GitHub، فرم وب یا پوشه سرور قرار گیرد.** فقط پاسخ دارای کلید عمومی و اثبات مالکیت کلید منتقل شود.

## ۴. احراز هویت مستقل و آماده‌کردن فهرست اعتماد

مالک/مسئول مجاز باید واقعاً هویت، صلاحیت، استقلال و تعارض منافع هر امضاکننده را بررسی و مدرک آن را محرمانه نگهداری کند. `prepare-registry` یک فایل `entries.json` می‌گیرد که آرایه‌ای از ورودی‌های زیر است:

```json
[
  {
    "invitation": "/secure/invite.json",
    "response": "/secure/answer.json",
    "identity_verification_record": "/secure/human-reviewed-identity-evidence.txt"
  }
]
```

این مرحله **به‌تنهایی احراز هویت نمی‌کند**؛ صرفاً تطبیق رمزنگاری‌شده کلید و مدارک را آماده می‌کند.

```bash
python3 "$WORK/factory_quality_reviewer_console_v1.py" prepare-registry \
  --workspace "$WORK" --entries /secure/entries.json
```

مالک، بعد از بازبینی انسانی، روی دستگاه مستقلِ مورد اعتماد، فایل پیشنهادی را با کلید خصوصی ریشه خود امضا می‌کند:

```bash
python3 factory_quality_reviewer_console_v1.py sign-registry \
  --proposal proposal.json \
  --root-private owner-root-private.pem \
  --root-public owner-root-public.pem \
  --output signed-registry.json
```

کلید خصوصی ریشه **نباید** به VPS منتقل شود.

## ۵. نصب فهرست امضاشده

بعد از انتقال فقط `signed-registry.json` به سرور و دریافت امنِ اثرانگشت کلید عمومی مالک:

```bash
python3 "$WORK/factory_quality_reviewer_console_v1.py" install-registry \
  --workspace "$WORK" \
  --signed-registry /secure/signed-registry.json \
  --root-sha256 ROOT_PUBLIC_KEY_SHA256_FROM_TRUSTED_CHANNEL
```

**الزام جداگانه:** اپراتور سرور باید اثرانگشت ریشه معتبر را در محیط امنِ فرایند اعتبارسنجی، با نام `FACTORY_QA_TRUST_ROOT_SHA256` پیکربندی کند. مقدار این متغیر را نباید از فایل ثبت متخصصان، ورودی مشتری یا رسید محصول به‌طور خودکار پذیرفت.

## ۶. امضای کیفیت نسخه دقیق محصول

هر متخصص باید مستقلاً شواهد و هر ۱۰۰ گروه را با جزئیات بررسی کند. **فقط وقتی همه گروه‌ها واقعاً ۱۰/۱۰، همه P0ها بسته و داده‌های نسخه صحیح است**:

```bash
python3 factory_quality_reviewer_console_v1.py sign-decision \
  --decision exact-build-decision.json \
  --private-key my-private-signing-key.pem \
  --reviewer-id independent_expert_001 \
  --role domain_specialist \
  --output my-decision-signature.json \
  --i-personally-reviewed-all-evidence
```

این امضا باید جداگانه برای نقش‌های متخصص علمی/فنی، ممیز مستقل، بررسی حقوقی و مالک گرفته شود. اگر مدارک واقعی موجود نباشد، **هیچ‌کس مجاز نیست ۱۰۰ نمره کامل را صرفاً برای بازکردن مسیر فروش ثبت کند.**

## معیار بهره‌برداری

بهره‌برداری از **زیرساخت خصوصی ثبت درخواست، مدیریت کلید عمومی و آزمون امضا** انجام شده است. بهره‌برداری از **صدور تأییدیه واقعی محصولات** فقط پس از معرفی و احراز هویت اشخاص واقعی، مشاهده اصل شواهد، امضای مستقل، پیکربندی ریشه اعتماد و تأییدِ اتصال به مسیر انتشار ممکن است.

آزمون نرم‌افزاریِ موفق به‌معنی تأیید علمی محصول نیست. امضای تستِ موقت به‌هیچ‌وجه مجوز انتشار نیست.
