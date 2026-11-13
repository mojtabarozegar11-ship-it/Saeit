# Mojtaba.Bot.Ai — Build Gate

## هدف

این پروژه تنها بستهٔ cBot مربوط به هویت canonical زیر را می‌سازد:

`Mojtaba.Bot.Ai.algo`

کلاس فعلی `MojTradeOmegaXDemoBot` یک ماژول اجرای دمو درون همین بسته است؛ هویت تجاری و عملیاتی جداگانه‌ای ایجاد نمی‌کند.

## پیش‌نیاز

- .NET 6 SDK (مطابق نسخهٔ فعلی cTrader.Automate 1.0.21)
- cTrader Automate package
- cTrader CLI نسخهٔ نصب‌شده
- بدون نیاز به credential برای مرحلهٔ build

## ساخت

از پوشهٔ `trading`:

```bash
dotnet restore Mojtaba.Bot.Ai.csproj
dotnet build Mojtaba.Bot.Ai.csproj -c Release
```

خروجی مورد انتظار:

```text
Mojtaba.Bot.Ai.algo
```

## ترتیب کنترل

1. Restore و build بدون credential، با Target Framework برابر net6.0.
2. بررسی وجود فایل خروجی و نام canonical.
3. اجرای `ctrader-cli metadata` فقط روی فایل محلی.
4. بک‌تست فقط با دادهٔ تاریخی یا حساب demo.
5. اجرای cBot واقعی و سفارش فقط پس از تأیید جداگانهٔ مالک.

## ممنوعیت‌ها

- credential، ورود حساب، سفارش و برداشت در build انجام نمی‌شود.
- حساب live مجاز نیست.
- حذف ربات‌های قدیمی بخشی از build نیست.
- موفقیت build به‌معنای سوددهی یا آماده‌بودن معامله نیست.
