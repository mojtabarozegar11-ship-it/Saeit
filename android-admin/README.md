# Saeit Android Admin

پنل مدیریت اندرویدی پروژه Saeit است و به API واقعی سایت متصل می‌شود.

## اتصال
- Base URL: https://zomorodmelal.ir
- احراز هویت: DRF Token Authentication
- فقط کاربران staff می‌توانند از مسیر احراز هویت اپ توکن بگیرند.
- توکن با EncryptedSharedPreferences روی دستگاه نگهداری می‌شود.

## قابلیت‌های فعلی
1. ورود مدیر و ذخیره امن نشست
2. داشبورد Agent / Task / Approval / Product / Order
3. مرکز تأیید مالک با تأیید یا رد مستقیم
4. گفت‌وگوی مالک با Master Agent
5. خروج و حذف توکن محلی
6. اتصال فقط از HTTPS به دامنه اصلی

## قانون کنترل
پاسخ چت به‌تنهایی به معنی اجرای موفق عملیات نیست؛ اجرای واقعی توسط Backend تعیین می‌شود و عملیات حساس از مسیر Approval عبور می‌کند.

## ساخت APK
در Android Studio یا محیطی با JDK 17 و Android SDK 35:

./gradlew assembleDebug

خروجی Debug: app/build/outputs/apk/debug/app-debug.apk

این ماژول به هیچ مخزن دیگری وابسته نیست و Commit، Push و Deploy خودکار انجام نمی‌دهد.
