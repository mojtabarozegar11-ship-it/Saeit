# Mojtaba.Bot.Ai — Build Gate

## هدف و مرز شواهد

تنها بستهٔ مورد قبول، `Mojtaba.Bot.Ai.algo` است. کلاس
`MojTradeOmegaXDemoBot` صرفاً ماژول داخلی همین بسته است؛ محصول یا
ربات مستقلی ایجاد نمی‌کند. موفقیت کامپایل به معنی سوددهی، آمادگی اجرای
Demo، اعتبارسنجی در cTrader CLI یا اجازهٔ معاملهٔ واقعی نیست.

## نسخه‌های تثبیت‌شده

- .NET 6 SDK (محدودیت cTrader.Automate نسخهٔ 1.0.21).
- نسخهٔ دقیق `cTrader.Automate=1.0.21` در پروژه pin شده است؛
  به‌روزرسانی وابستگی نیازمند بررسی جداگانه است.
- محیط GitHub-hosted صرفاً برای Restore، Build و بررسی آفلاین فایل است.
- بدون حساب کارگزاری، credential، سفارش، انتقال وجه یا VPS.

## علت گیت پیشین و راه‌حل

در اجرای قبلی، کامپایل موفق بود اما `Saeit.algo` در مسیر
`net6.0` ساخته شد، درحالی‌که CI مسیر قدیمی
`net8.0/Mojtaba.Bot.Ai.algo` را جست‌وجو می‌کرد.
در برخی نسخه‌های بستهٔ cTrader نام فایل از نام پوشهٔ ریشهٔ پروژه
گرفته می‌شود؛ تغییر نام فایل پس از Build اثبات هویت نیست.
بنابراین Workflow پروژه و کد مورد بررسی را داخل پوشهٔ موقت و
ایزولهٔ `Mojtaba.Bot.Ai` کپی و همان‌جا Build می‌کند.

## اجرای همان Build در محیط Linux/macOS

از ریشهٔ مخزن:

```bash
set -euo pipefail
bot_root="$(mktemp -d)/Mojtaba.Bot.Ai"
mkdir -p "$bot_root"
cp trading/Mojtaba.Bot.Ai.csproj "$bot_root/"
cp trading/MojTradeOmegaXDemoBot.cs "$bot_root/"
dotnet restore "$bot_root/Mojtaba.Bot.Ai.csproj"
dotnet build "$bot_root/Mojtaba.Bot.Ai.csproj" --configuration Release --no-restore
output="$bot_root/bin/Release/net6.0"
test -s "$output/Mojtaba.Bot.Ai.algo"
test ! -e "$output/Saeit.algo"
test ! -e "$output/MojTradeOmegaXDemoBot.algo"
sha256sum "$output/Mojtaba.Bot.Ai.algo"
```

## گیت‌های مستقل بعد از Build

1. موفقیت تمام مراحل CI و وجود دقیقاً یک خروجی canonical.
2. بررسی metadata واقعی با cTrader CLI رسمی در محیط سازگار.
3. اجرای Backtest روی دادهٔ تاریخی واقعی با اسپرد و هزینهٔ معامله.
4. آزمون Demo با کنترل ریسک و ثبت رسید.
5. هرگونه استقرار و معاملهٔ واقعی فقط پس از تأیید مجزای مالک.

تا تحقق این موارد، PR در حالت Draft باقی می‌ماند.
