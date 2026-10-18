#!/usr/bin/env python3
"""Create an individual, crawlable scientific introduction for every Zomorod homepage card.

Input: verified 29-row live homepage, *not* a hardcoded old fixture.
Outputs: a candidate homepage and /topics/ staging folder. No direct writes
to the live document root. 60 earlier research pages are preserved and linked.
All 545 other cards get unique canonical URLs, a standalone page, research
methodology and domain-specific metrics, accurate descriptions and JSON-LD.

The texts describe scientific disciplines and evaluation methods; they do not
invent company projects, lab certifications, expertise credentials or results.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

VERSION = "zm-all-cards-dedicated-topics-20261018"
BASE = "https://zomorodmelal.ir"
PUBLISHED = "2026-10-18"
MANIFEST_RE = re.compile(r'(window\.ZOMOROD_ORBIT_DATA=)(\{.*?\})(;</script>)', re.S)
# Domain-specific frameworks: deliberately distinct research models, measures
# and constraints for the 26 established homepage shelves.
FIELDS = {
"ZM-R01": (
"تولیدات گیاهی به تحلیل هم‌زمان ژنوتیپ، خاک، مدیریت زراعی و اقلیم نیاز دارند. عملکرد مشاهده‌شده یک متغیر مستقل از شرایط مزرعه نیست و باید همراه با داده‌های مدیریتی تفسیر شود.",
"طرح‌های بلوک کامل تصادفی، تکرار مزرعه‌ای، پایش فنولوژی و تحلیل اثر سال و منطقه می‌توانند برای آزمون فرضیه مناسب باشند. واحد آزمایشی و تعداد تکرار باید پیش از گردآوری داده تعیین شوند.",
"عملکرد در واحد سطح، بهره‌وری مصرف آب، شاخص برداشت، پایداری عملکرد، کیفیت محصول و تغییرپذیری بین فصل‌ها شاخص‌هایی‌اند که بر اساس پرسش مشخص انتخاب می‌شوند.",
"کنترل اثر بافت خاک، تاریخ کاشت، تراکم، تغذیه، بیماری، دما و بارش برای جلوگیری از نسبت دادن نادرست تفاوت عملکرد به یک عامل ضروری است.",
"برآورد اقتصادی باید هزینه نهاده، آب، انرژی، عملیات و ریسک نوسان عملکرد را کنار کیفیت محصول قرار دهد؛ توصیه واحد برای همه اقلیم‌ها اعتبار علمی ندارد."),
"ZM-R02": (
"پژوهش باغبانی چرخه رشد گیاهان یک‌ساله و چندساله را با فیزیولوژی، روابط پایه و پیوندک، کیفیت میوه و مدیریت پس از برداشت پیوند می‌دهد.",
"طرح‌های مشاهده‌ای طولی، آزمایش چندفصلی و مقایسه رقم و محیط برای جداکردن اثر اقلیم از صفات گیاهی اهمیت دارند؛ دوره ارزیابی باید متناسب با زیست‌شناسی گونه تعیین شود.",
"زمان گل‌دهی و رسیدگی، عملکرد، صفات حسی و فیزیکی میوه، بریکس، اسیدیته، ماندگاری و شاخص‌های تنش بسته به موضوع قابل اندازه‌گیری‌اند.",
"اثر سن باغ، هرس، مدیریت آبیاری، تغذیه، سرمای موردنیاز و آفات باید ثبت شود؛ یک فصل پربار الزاماً به معنای پایداری عملکرد در سال‌های بعد نیست.",
"توصیه اجرایی زمانی قابل دفاع است که کیفیت، ریسک اقلیمی، هزینه نگهداری و پاسخ بازار در ارزیابی چندساله بررسی شده باشند."),
"ZM-R03": (
"سامانه گلخانه یک سامانه کنترل‌شده زیستی-مهندسی است و طراحی آن باید روابط نور، دما، رطوبت، تهویه، آب، تغذیه و مصرف انرژی را هم‌زمان لحاظ کند.",
"حسگرهای کالیبره، ثبت سری زمانی، طراحی آزمایش کنترل متغیرها و تحلیل پاسخ گیاه به نقطه تنظیم محیط برای ارزیابی فرایند مناسب‌اند.",
"تابش فعال فتوسنتزی، کسری فشار بخار VPD، هدایت الکتریکی محلول EC، pH، دمای ریشه، بازده آب و انرژی به ازای محصول از شاخص‌های متداول هستند.",
"ناهمگنی مکانی محیط، سایه‌اندازی، بیماری‌های وابسته به رطوبت و خطای حسگرها می‌توانند نتایج را منحرف کنند و نیازمند آزمون صحت‌اند.",
"پیش از توسعه مقیاس باید هم کیفیت محصول و هم هزینه سرمایه‌گذاری، تعمیرات، انرژی و پایداری تأمین نهاده‌ها ارزیابی شود."),
"ZM-R04": (
"علوم دامپروری نیازمند پیوند فیزیولوژی، تغذیه، ژنتیک، بهداشت و اقتصاد تولید است؛ بهبود یک شاخص نباید با کاهش رفاه جانوران به دست آید.",
"پژوهش مناسب از ثبت داده‌های فردی و گله‌ای، گروه‌های مقایسه همسان و تحلیل عوامل مخدوش‌گر سن، نژاد، جیره و محیط استفاده می‌کند.",
"شاخص‌های رشد، تولید، ضریب تبدیل خوراک، وضعیت تولیدمثل، سلامت و شاخص‌های رفاه حیوان باید بر حسب نوع سامانه انتخاب شوند.",
"در طراحی مطالعه باید سوگیری انتخاب دام، شیوع بیماری، تنش حرارتی، کیفیت خوراک و خطای ثبت وزن یا تولید کنترل شوند.",
"تفسیر اقتصادی باید هزینه خوراک، دامپزشکی، نیروی کار، ضایعات و چرخه تولید را در کنار الزامات بهداشتی و اخلاق پژوهش قرار دهد."),
"ZM-R05": (
"مدیریت علمی طیور مجموعه‌ای از ژنتیک، تغذیه، بهداشت گله، تهویه، نور و رفتار جانوران را شامل می‌شود.",
"پایش دسته‌ای با تعریف دقیق واحد آزمایشی، ثبت مصرف خوراک و شرایط محیطی و تحلیل اختلاف گله‌ها از روش‌های مناسب ارزیابی است.",
"تلفات و ماندگاری گله، ضریب تبدیل خوراک، رشد یا تولید تخم‌مرغ، کیفیت پوسته و شاخص‌های بهداشت بر اساس نوع پرنده سنجیده می‌شوند.",
"تراکم پرورش، کیفیت بستر، آمونیاک، تهویه، برنامه نوری و عوامل بیماری‌زا باید در مقایسه نتایج مدیریت شوند.",
"هر راهبرد عملیاتی باید با الزامات دامپزشکی، ایمنی زیستی، رفاه طیور و امکان‌سنجی هزینه تولید منطبق باشد."),
"ZM-R06": (
"پرورش آبزیان سامانه‌ای وابسته به کیفیت آب، زیست‌شناسی گونه، تغذیه و کنترل بیماری است و انتقال روش‌ها میان گونه‌ها بدون اعتبارسنجی ممکن نیست.",
"طراحی آزمایش با تکرار مخزن یا حوضچه، نمونه‌برداری منظم آب و ثبت زیست‌توده برای تفکیک اثر مدیریت از تغییر محیط ضرورت دارد.",
"اکسیژن محلول، pH، دما، نیتروژن آمونیاکی، نرخ رشد ویژه SGR، ضریب تبدیل خوراک و بقا نمونه شاخص‌های علمی این حوزه‌اند.",
"تغییرات شبانه‌روزی آب، خطای سنجش کیفیت، تراکم ذخیره‌سازی و انتقال عوامل بیماری‌زا باید کنترل شود.",
"ارزیابی تولید باید مصرف آب و انرژی، هزینه خوراک، تلفات، ریسک بیماری و آثار زیست‌محیطی پساب را شامل شود."),
"ZM-R07": (
"کیفیت بذر، نهال و نهاده تنها با نام تجاری یا ادعای فروشنده تعیین نمی‌شود؛ هویت، خلوص، سلامت و انطباق با استاندارد فنی باید بررسی شوند.",
"نمونه‌برداری نماینده، آزمون‌های مقایسه‌ای و زنجیره ردیابی بچ محصول، مبنای پژوهش و کنترل کیفیت نهاده‌ها هستند.",
"درصد جوانه‌زنی، خلوص ژنتیکی، قوه نامیه، رطوبت، ترکیب ماده مؤثر، یکنواختی و پایداری در انبار بسته به نوع محصول قابل ارزیابی است.",
"تاریخ تولید، شرایط حمل، آلودگی، اثر محیط و روش نگهداری بر کیفیت مؤثرند و بدون ثبت آن‌ها نتیجه قابل تعمیم نیست.",
"ادعاهای عملکرد یا عرضه هر نهاده مستلزم ضوابط ثبت و برچسب‌گذاری و شواهد کاربرد در شرایط واقعی است."),
"ZM-R08": (
"ژنتیک و به‌نژادی مطالعه وراثت، تنوع ژنی، ساختار جمعیت و برهم‌کنش ژنوتیپ و محیط است؛ نشانگر مولکولی جایگزین مشاهده معتبر فنوتیپ نمی‌شود.",
"طرح نمونه‌گیری متوازن، کنترل کیفیت داده ژنوتیپی، آزمایش‌های چندمحیطی و تحلیل آماری ساختار جمعیت از پایه‌های استنتاج معتبر هستند.",
"فراوانی آلل، تنوع ژنتیکی، وراثت‌پذیری، همبستگی صفات، ارزش ژنتیکی و پاسخ به انتخاب باید با فاصله اطمینان مناسب گزارش شوند.",
"اثرات خویشاوندی، ساختار جمعیت، چندآزمونی، خطاهای ژنوتیپ‌خوانی و سوگیری محیطی در تحلیل باید کنترل شوند.",
"حفاظت از ذخایر ژنتیکی، رفاه موجود زنده و مقررات دسترسی به منابع ژنتیکی در طراحی و بهره‌برداری اهمیت دارد."),
"ZM-R09": (
"مدیریت آب و خاک به پیوند هیدرولوژی، فیزیک خاک، کیفیت آب، نیاز گیاه و شرایط اقلیمی وابسته است.",
"پروفیل خاک، سری زمانی رطوبت و هواشناسی، آزمون نفوذپذیری و مدل تراز آب در کنار سنجش مزرعه‌ای برای برآورد مناسب‌اند.",
"تبخیر و تعرق، راندمان کاربرد آب، شوری EC، نسبت جذب سدیم SAR، رطوبت حجمی، ظرفیت نگهداری و بهره‌وری آب از شاخص‌ها هستند.",
"ناهمگنی خاک، تبخیر سطحی، رواناب، زهکشی، عملکرد حسگر و تغییرپذیری بارش باید در عدم‌قطعیت تحلیل لحاظ شوند.",
"تصمیم آبیاری و اصلاح خاک باید خطر شوری، محدودیت منابع آب، هزینه انرژی و پایداری سامانه را هم‌زمان بسنجد."),
"ZM-R10": (
"ماشین‌آلات کشاورزی را باید به‌صورت یک سامانه مکانیکی-انسانی مرتبط با خاک، گیاه، سوخت و زمان‌بندی عملیات بررسی کرد.",
"آزمون میدانی با شرایط خاک و بار کاری ثبت‌شده، اندازه‌گیری توان و سوخت و تکرارهای قابل مقایسه از روش‌های ارزیابی عملکرد‌اند.",
"ظرفیت مؤثر مزرعه‌ای، مصرف سوخت بر واحد کار، راندمان مکانیکی، افت محصول، زمان توقف و هزینه هر هکتار شاخص‌های قابل سنجش‌اند.",
"رطوبت خاک، تنظیم ادوات، سرعت پیشروی، مهارت اپراتور و فرسودگی قطعات باید در آزمایش کنترل شوند.",
"انتخاب فناوری باید به ایمنی کاربر، تعمیرپذیری، قطعات یدکی، عمر اقتصادی و تناسب با اندازه مزرعه وابسته باشد."),
"ZM-R11": (
"صنعت و فرآوری بر تبدیل مواد اولیه به محصول با کیفیت پایدار، ایمنی قابل ردیابی و بهره‌وری انرژی و مواد متمرکز است.",
"تحلیل جریان مواد و انرژی، ارزیابی نقاط کنترل بحرانی، آزمون پایداری محصول و اعتبارسنجی فرایند از ابزارهای پژوهش کاربردی‌اند.",
"بازده تبدیل، ضایعات، مصرف انرژی، بار میکروبی، کیفیت فیزیکی و شیمیایی، عمر ماندگاری و نرخ عدم‌انطباق بسته به موضوع انتخاب می‌شوند.",
"تفاوت بچ مواد اولیه، تغییرات دما و رطوبت، آلودگی متقاطع و عدم‌قطعیت دستگاه‌های اندازه‌گیری باید کنترل شود.",
"هر توسعه صنعتی به بررسی ایمنی محصول، مجوزهای مرتبط، بازار هدف، اقتصاد مقیاس و مدیریت پسماند نیاز دارد."),
"ZM-R12": (
"پژوهش علمی با پرسش دقیق، مرور انتقادی پیشینه و آزمون‌پذیری فرضیه تعریف می‌شود؛ تولید حجم زیادی از متن به‌تنهایی پژوهش نیست.",
"تعریف طرح، پروتکل پیشینی، انتخاب حجم نمونه، گروه کنترل مناسب و طرح تحلیل مستقل از نتیجه برای کاهش سوگیری توصیه می‌شود.",
"اندازه اثر، فاصله اطمینان، حساسیت مدل، قابلیت تکرار، کیفیت داده و میزان تحقق هدف از شاخص‌های ارزیابی پژوهش هستند.",
"خطای اندازه‌گیری، سوگیری انتشار، مخدوش‌گرها، چندگانگی آزمون و تعمیم فراتر از داده باید صریح گزارش شوند.",
"توسعه فناوری تنها پس از اعتبارسنجی بیرونی، امکان‌سنجی فنی و اقتصادی و بررسی الزامات اخلاقی و قانونی قابل طرح است."),
"ZM-R13": (
"سامانه‌های داده و هوش مصنوعی زمانی برای پژوهش مفیدند که مسئله واقعی، داده قابل اعتماد و معیار موفقیت مشخص باشد.",
"طرح تحلیل نیازمند تقسیم درست آموزش و آزمون، جلوگیری از نشت داده، ارزیابی بیرونی و مقایسه با خط مبنای ساده است.",
"دقت پیش‌بینی، حساسیت، ویژگی، خطای برآورد، کالیبراسیون، پایداری در تغییر توزیع و هزینه محاسباتی شاخص‌های انتخابی‌اند.",
"سوگیری نمونه‌گیری، تغییر توزیع داده، محرمانگی، امنیت و قابلیت تبیین باید در توسعه و استقرار ارزیابی شوند.",
"هر تصمیم حساس علمی، مالی، پزشکی یا تولیدی به راستی‌آزمایی انسانی و مدیریت ریسک متناسب نیاز دارد."),
"ZM-R14": (
"آموزش حرفه‌ای مبتنی بر شایستگی به تعیین سطح ورودی، هدف یادگیری و سنجش توان کاربرد دانش نیاز دارد.",
"طراحی آموزشی با تحلیل نیاز مخاطب، اهداف قابل سنجش، تمرین مسئله‌محور و آزمون پیش و پس از آموزش ارزیابی می‌شود.",
"میزان تحقق شایستگی، کیفیت پروژه عملی، تداوم یادگیری، رضایت آگاهانه و انتقال مهارت به محیط کار از شاخص‌های مناسب‌اند.",
"تناسب محتوا با سطح مخاطب، صحت منابع، دسترس‌پذیری و ارزیابی مستقل مدرسان اهمیت دارد.",
"اعلام دوره، مدرک یا گواهی رسمی فقط با احراز دوره واقعی، صلاحیت مجری و شرایط قانونی صحیح است."),
"ZM-R15": (
"فعالیت خدماتی و پروژه‌ای باید با نیازسنجی و دامنه کار قابل سنجش تعریف شود؛ معرفی یک خدمت معادل تعهد به ارائه آن نیست.",
"تحلیل ذی‌نفعان، ارزیابی ریسک، برنامه زمان‌بندی، ساختار شکست کار و کنترل نسخه اسناد در مدیریت پروژه کاربرد دارند.",
"کیفیت تحویل، زمان اجرا، انحراف هزینه، رضایت مشتری، نرخ خطا و شاخص‌های توافق‌شده قرارداد باید شفاف باشند.",
"ابهام دامنه، تغییرات بدون کنترل، تضاد منافع، عدم احراز مجوز و وابستگی به پیمانکاران می‌تواند ریسک ایجاد کند.",
"هر همکاری نیازمند قرارداد معتبر، بررسی ظرفیت واقعی، حفاظت داده و ارزیابی فنی و اقتصادی است."),
"ZM-R16": (
"هویت سازمانی معتبر بر مأموریت روشن، ساختار پاسخ‌گویی، اطلاعات قابل ردیابی و تفکیک ادعای سازمان از دستاورد مستند استوار است.",
"تدوین شناسنامه سازمانی باید از اسناد حقوقی، ساختار اعلام‌شده، سیاست‌های رسمی و ارزیابی صحت اطلاعات شروع شود.",
"دقت اطلاعات تماس، به‌روزبودن معرفی مسئولیت‌ها، انسجام پیام، قابلیت دسترسی و شفافیت وضعیت طرح‌ها از شاخص‌های کیفیت ارتباط‌اند.",
"ادعاهای رتبه، بزرگی، اخذ مجوز، همکاری و تأمین مالی باید با سند قابل اتکا تأیید شوند.",
"رسانه سازمان باید میان چشم‌انداز آینده، برنامه در دست بررسی و فعالیت تحقق‌یافته مرز روشنی داشته باشد."),
"ZM-R17": (
"اطلاع‌رسانی علمی و سازمانی باید تاریخ رویداد، تاریخ انتشار، منشأ اطلاعات و وضعیت تأیید آن را مشخص کند.",
"راستی‌آزمایی چندمنبعی، تفکیک خبر از تحلیل و ثبت اصلاحیه‌ها در فرایند انتشار معتبر اهمیت دارد.",
"دقت عنوان، ارجاع به اسناد، اعتبار منبع، زمان‌بندی و امکان پیگیری اصلاحیه شاخص‌های سنجش کیفیت خبرند.",
"خبر تأییدنشده یا رویدادی که واقعاً رخ نداده نباید به‌عنوان دستاورد یا اطلاعیه رسمی منتشر شود.",
"این صفحات فهرست موضوعات پوشش خبری هستند و در نبود خبر واقعی، صرفاً حوزه موضوعی را معرفی می‌کنند."),
"ZM-R18": (
"پژوهش صنایع غذایی بر ایمنی، ترکیب، کیفیت حسی و تغذیه‌ای، فرایند و رفتار محصول در نگهداری متمرکز است.",
"اعتبارسنجی فرایند، طرح نمونه‌برداری بچ، مطالعه عمر ماندگاری و تحلیل خطر در تولید مواد غذایی به کار می‌روند.",
"فعالیت آبی، pH، بار میکروبی، بازده فرآوری، ترکیب تغذیه‌ای، پایداری و پذیرش حسی باید بر حسب محصول سنجیده شوند.",
"آلودگی متقاطع، تغییر مواد اولیه، زنجیره سرد، خطای نمونه‌برداری و تفاوت شرایط مصرف در تحلیل مهم‌اند.",
"توسعه محصول نیازمند رعایت مقررات برچسب‌گذاری و ایمنی است؛ ادعای فراسودمندی یا سلامت بدون پشتوانه علمی مجاز نیست."),
"ZM-R19": (
"مهندسی کارخانه رابطه ظرفیت خط، جریان مواد، انرژی، تعمیرات و کیفیت تحویل محصول را به‌صورت یک سامانه بررسی می‌کند.",
"نقشه جریان ارزش، تحلیل گلوگاه، ثبت توقف ماشین و شبیه‌سازی ظرفیت به همراه اعتبارسنجی داده عملیاتی ابزارهای ارزیابی هستند.",
"اثربخشی کلی تجهیزات OEE، ظرفیت واقعی، ضایعات، زمان چرخه، شدت مصرف انرژی و هزینه واحد محصول معیارهای متداول‌اند.",
"تغییر ترکیب سفارش‌ها، خرابی پیش‌بینی‌نشده، کیفیت تأمین‌کنندگان و خطرات ایمنی می‌توانند نتایج را جابه‌جا کنند.",
"تصمیم سرمایه‌گذاری باید هزینه چرخه عمر، دسترس‌پذیری قطعه، ایمنی کارکنان و ریسک توقف تولید را لحاظ کند."),
"ZM-R20": (
"مهندسی عمران و ساختمان بر هماهنگی طراحی، اجرا، مصالح، ایمنی سازه، محیط و چرخه عمر دارایی استوار است.",
"بررسی سازه و خاک، کنترل محاسبات، تست مصالح، برنامه‌ریزی ساخت و کنترل کیفیت اجرا باید متناسب با استانداردهای محل انجام شود.",
"شاخص‌های مقاومت، دوام، تغییرشکل، بهره‌وری انرژی، زمان و هزینه پروژه و عدم‌انطباق فنی بر اساس موضوع قابل سنجش‌اند.",
"خطای نقشه، شرایط زمین، تغییرات بارگذاری، کیفیت اجرا و تأخیر تأمین مصالح از ریسک‌های اصلی هستند.",
"ارائه نظر مهندسی رسمی، طراحی یا نظارت قانونی تنها با مجوز حرفه‌ای و مسئولیت مشخص انجام می‌شود."),
"ZM-R21": (
"ارزیابی املاک و مستغلات ترکیبی از تحلیل بازار، حقوق مالکیت، کاربری زمین و محاسبات مالی با عدم‌قطعیت بالاست.",
"مقایسه معاملات همسان، تحلیل جریان نقدی تنزیل‌شده و سناریوسازی نرخ بهره و تقاضا روش‌های قابل مطالعه‌اند.",
"قیمت مقایسه‌ای، بازده اجاره، نرخ خالی‌ماندن، ارزش فعلی خالص و حساسیت به هزینه نگهداری از متغیرهای کلیدی‌اند.",
"کمبود داده معاملات، تفاوت موقعیت، محدودیت‌های ثبتی و تغییر مقررات می‌تواند نتیجه ارزش‌گذاری را دگرگون کند.",
"محتوا جنبه آموزشی دارد و جایگزین ارزیابی رسمی، مشاوره حقوقی یا توصیه سرمایه‌گذاری شخصی نیست."),
"ZM-R22": (
"علوم طلا، جواهر و گوهرسنگ نیازمند شناخت خواص مواد، اصالت‌سنجی، کنترل عیار و سازوکار قیمت‌گذاری است.",
"آزمون مناسب بر اساس جنس نمونه، روش غیرمخرب یا مخرب، استاندارد ابزار و زنجیره مستند مالکیت انتخاب می‌شود.",
"عیار، جرم خالص، عدم‌قطعیت سنجش، کیفیت تراش، منشأ مستند و قیمت مرجع از داده‌های مهم هستند.",
"خطای ترازو، ناخالصی آلیاژ، بهسازی گوهر، تقلب و نوسان قیمت بازار باید در ارزیابی لحاظ شوند.",
"خرید و فروش و عیارسنجی رسمی نیازمند مجوزهای مربوط است و محتوای آموزشی جایگزین قیمت یا استعلام معتبر نیست."),
"ZM-R23": (
"فرش و صنایع دستی را می‌توان از منظر مواد، تکنیک ساخت، تاریخ هنر، اصالت و اقتصاد فرهنگی مطالعه کرد.",
"ارزیابی الیاف، ساختار گره، رنگ، وضعیت حفاظتی و مستندسازی منشأ با روش‌های غیرمخرب اولویت دارد.",
"تراکم بافت، کیفیت ماده اولیه، اصالت طرح، پایداری رنگ، ابعاد و وضعیت مرمت از شاخص‌های قابل ثبت هستند.",
"تفاوت سنت محلی، شرایط نگهداری، فرسودگی و تغییرات بازار سبب می‌شود ارزش‌گذاری نیازمند بررسی موردی باشد.",
"حفاظت از میراث فرهنگی و شفافیت درباره اصالت، مرمت و قیمت‌گذاری از اصول معرفی و تجارت مسئولانه است."),
"ZM-R24": (
"صنایع مهمان‌داری و آشپزی به مدیریت ایمنی غذا، رفتار مصرف‌کننده، کیفیت خدمت و اقتصاد عملیات وابسته‌اند.",
"مطالعه فرایند تهیه غذا، ارزیابی خطر، ثبت کیفیت بچ و تحلیل بازخورد مشتری برای اصلاح فرایند مفید است.",
"کنترل دمای ایمن، زمان خدمت، ضایعات، بهای تمام‌شده، رضایت و شاخص‌های بهداشت بر حسب خدمت انتخاب می‌شوند.",
"تغییر مواد اولیه، خطای کنترل دما، آلودگی متقاطع، آلرژن‌ها و وابستگی به نیروی انسانی از عوامل ریسک‌اند.",
"ارائه خدمات غذایی واقعی نیازمند مجوز، نظام بهداشت، توان عملیاتی و گزارش صادقانه ویژگی‌های محصول است."),
"ZM-R25": (
"توسعه خدمات دیجیتال به معماری سامانه، تجربه کاربری، امنیت داده و الزامات عملیاتی بلندمدت وابسته است.",
"تعریف نیازمندی، نمونه اولیه، آزمون واحد و یکپارچگی، پایش عملکرد و تحلیل تهدید از اجزای چرخه مهندسی هستند.",
"دسترس‌پذیری، تأخیر پاسخ، خطای سرویس، قابلیت نگهداری، امنیت و رضایت کاربر شاخص‌های انتخابی‌اند.",
"ریسک‌های حریم خصوصی، وابستگی نرم‌افزاری، نقص کنترل دسترسی و خطای استقرار باید ارزیابی شوند.",
"وعده عملکرد یا امنیت کامل بدون شواهد آزمون و شرایط پشتیبانی روشن قابل دفاع نیست."),
"ZM-R26": (
"برنامه‌ریزی گردشگری و رویداد به شناخت تقاضا، ظرفیت مقصد، تجربه بازدیدکننده و آثار محیطی و اجتماعی نیاز دارد.",
"مطالعه پیمایشی، تحلیل جریان بازدیدکنندگان، ارزیابی دسترس‌پذیری و سناریوسازی ازدحام برای بررسی مناسب‌اند.",
"میزان رضایت، ظرفیت قابل تحمل، کیفیت خدمت، هزینه هر رویداد و پیامد اقتصادی و محیطی از شاخص‌ها هستند.",
"فصلی‌بودن تقاضا، ایمنی جمعیت، تغییر مقررات و آثار گردشگری بر جامعه محلی از عدم‌قطعیت‌های مهم‌اند.",
"معرفی یک تور یا خدمت به معنای امکان رزرو یا اجرای واقعی نیست؛ ارائه خدمات وابسته به مجوز و ظرفیت تأییدشده است."),
}
assert len(FIELDS)==26 and all(len(v)==5 for v in FIELDS.values())
DETAILS = (
("ژنتیک", "در تحلیل این موضوع، تفسیر تنوع ژنتیکی باید به داده‌های فنوتیپی و عوامل محیطی متصل شود؛ نسبت‌دادن مستقیم صفات پیچیده به یک نشانگر بدون بررسی خطا قابل دفاع نیست."),
("اصلاح", "اولویت‌های اصلاحی باید در قالب شاخص انتخاب مشخص شوند و خطر کاهش تنوع ژنتیکی، برهم‌کنش ژن و محیط و بازده بلندمدت بررسی شود."),
("بذر", "ارزیابی علمی این موضوع به ثبت منبع بذر، یکنواختی نمونه، درصد جوانه‌زنی و شرایط نگهداری نیاز دارد؛ نتایج باید با روش مرجع تطبیق شوند."),
("آبیاری", "موازنه آب، نیاز واقعی گیاه، تلفات سامانه و تغییرپذیری مکانی خاک باید پیش از هر توصیه مدیریت آبیاری برآورد شوند."),
("خاک", "برای تفسیر نتایج لازم است عمق و زمان نمونه‌برداری، بافت، شوری، مواد آلی و محدودیت‌های روش آزمون ثبت شود."),
("گلخانه", "کنترل مستقل شرایط محیطی، وضعیت حسگرها، مصرف انرژی و شاخص‌های عملکرد گیاه شرط تفسیر آزمون گلخانه‌ای است."),
("کیفیت", "کیفیت باید به شاخص‌های آزمون‌پذیر و حدود پذیرش مرتبط با کاربری تعریف شود، نه صرفاً برچسب ممتاز یا ادعای فروش."),
("ایمنی", "تحلیل خطر و ارزیابی سناریوهای خطا باید متناسب با پیامدهای انسانی و محیطی انجام شود؛ مجوز حرفه‌ای جایگزین بررسی علمی نیست."),
("بازار", "نتایج مطالعه بازار باید با منبع، بازه زمانی، داده مقایسه‌ای و سناریوی عدم‌قطعیت گزارش شوند."),
("مالی", "ارزیابی اقتصادی باید بین درآمد تحقق‌یافته، برآورد سناریویی و تعهدات قطعی تمایز بگذارد و حساسیت به هزینه و تقاضا را تحلیل کند."),
("هوش", "استفاده از الگوریتم‌ها باید همراه با مجموعه آزمون مستقل، سنجش سوگیری و روش کنترل تغییر عملکرد در زمان باشد."),
("داده", "کیفیت داده، تعریف متغیر، مقدارهای مفقود و قابلیت ردیابی تبدیل‌های تحلیلی شرط تفسیر درست نتایج است."),
("دام", "در مطالعات این موضوع باید سلامت، رفاه، سن و جیره در کنار شاخص‌های تولیدی و ژنتیکی ثبت شوند."),
("طیور", "نقش تراکم، کیفیت بستر، نور، جیره و عوامل بیماری‌زا باید در تحلیل عملکرد گله کنترل شود."),
("آبزی", "کیفیت و نوسان آب، زیست‌توده، وضعیت خوراک و زیست‌امنیتی از متغیرهای کلیدی ارزیابی هستند."),
("غذا", "تغییر ترکیب مواد اولیه، بار میکروبی، کیفیت فرآوری و شرایط نگهداری در سنجش این موضوع اهمیت دارند."),
("میکروب", "کنترل آلودگی، سطح ایمنی زیستی، روش شناسایی و تکرارپذیری نتایج باید در پروتکل تعریف شود."),
("ساختمان", "مقررات محل، شرایط بستر، دوام، ایمنی کارگاه و بازرسی مستقل از الزام‌های بررسی این موضوع‌اند."),
("کارخانه", "شناخت گلوگاه فرایند، تراز مواد و انرژی، ایمنی عملیات و هزینه چرخه عمر در تصمیم فنی اهمیت دارد."),
("آموزش", "اثر آموزش باید با خروجی یادگیری و توان انجام فعالیت واقعی سنجیده شود، نه فقط تعداد شرکت‌کنندگان."),
("پژوهش", "پروتکل قابل تکرار، گروه مقایسه، عدم‌قطعیت و امکان بازبینی داده‌ها باید قبل از اعلام نتیجه پژوهش مشخص باشد."),
("تولید", "تحلیل ظرفیت واقعی، کنترل فرایند، کیفیت خروجی و ضایعات برای ارزیابی اقتصادی و فنی لازم است."),
("تجارت", "ریسک تأمین و تعهدات حقوقی، کیفیت مستند محصول و شفافیت قیمت باید ارزیابی شوند."),
("زیست", "تعامل عوامل زیستی و غیرزیستی، محدودیت مقیاس و امکان تعمیم یافته‌ها به شرایط عملیاتی باید بررسی شود."),
("نرم", "در ارزیابی سامانه باید نیازمندی قابل آزمون، کنترل امنیتی، تداوم خدمت و دسترس‌پذیری تعریف شود."),
)
def e(x): return html.escape(str(x),quote=True)
def norm(x): return re.sub(r'\s+',' ',x.strip())
def details(title, card_id):
    matches=[p for word,p in DETAILS if word in title]
    if not matches:
        seed=int(hashlib.sha256(card_id.encode()).hexdigest()[:8],16)
        matches=[
          "برای این موضوع، ابتدا معیار ورود نمونه و روش سنجش تعریف و سپس اثر شرایط محیطی، محدودیت منابع و دقت ابزار بررسی می‌شود.",
          "جداسازی اثر واقعی از تغییرات تصادفی به تکرار مناسب، انتخاب شاخص معتبر و ثبت کامل شرایط اجرای مطالعه وابسته است.",
          "انتقال یافته‌ها به مقیاس واقعی باید پس از ارزیابی مستقل، تحلیل هزینه-فایده و شناسایی سناریوهای شکست انجام شود.",
        ]
        return matches[seed % len(matches)]
    return " ".join(matches[:2])
def topic_page(card,row,original_url):
    rid=row["id"]; title=norm(card["title"]); group=norm(row["title"])
    theory,design,metrics,control,decision=FIELDS[rid]
    path=f"/topics/{rid.lower()}/{card['slug']}/"; canon=BASE+path
    desc=norm(f"معرفی علمی {title} در حوزه {group}: مبانی تخصصی، روش‌های ارزیابی، شاخص‌های فنی، محدودیت‌های پژوهش و ملاحظات کاربردی | زمرد ملل.")
    if len(desc)>190:desc=desc[:186].rstrip(" ،.")+"."
    tag=e(title+" | "+group+" | زمرد ملل")
    url_json=json.dumps(canon,ensure_ascii=False)
    graphic=f"https://zomorodmelal.ir/static/site/zomorod-v7/company-logo.webp"
    structured=[
      {"@context":"https://schema.org","@type":"WebPage","inLanguage":"fa-IR",
       "name":f"{title} | {group} | زمرد ملل","url":canon,
       "description":desc,"isPartOf":{"@type":"WebSite","name":"زمرد ملل","url":BASE+"/"},
       "publisher":{"@type":"Organization","name":"شرکت کشت و صنعت زمرد ملل","url":BASE+"/"}},
      {"@context":"https://schema.org","@type":"BreadcrumbList",
       "itemListElement":[{"@type":"ListItem","position":1,"name":"خانه","item":BASE+"/"},
       {"@type":"ListItem","position":2,"name":"دانشنامه موضوعات","item":BASE+"/topics/"},
       {"@type":"ListItem","position":3,"name":group,"item":BASE+f"/topics/#{rid.lower()}"},
       {"@type":"ListItem","position":4,"name":title,"item":canon}]}
    ]
    schema=json.dumps(structured,ensure_ascii=False).replace("</","<\\/")
    origlink=""
    if original_url and original_url!=path and original_url.startswith("/") and not original_url.startswith("//"):
        origlink=f'<a href="{e(original_url)}">صفحه موجود مرتبط با این موضوع</a>'
    # Include the *existing* card illustration only when it is self-contained SVG,
    # otherwise provide a distinct lightweight subject-matched SVG for accessibility.
    seed=int(hashlib.sha256((rid+":"+card["slug"]).encode()).hexdigest()[:12],16)
    hue=(seed%105)+96
    visual=(f'<svg viewBox="0 0 680 280" role="img" aria-label="تصویرسازی مفهومی مرتبط با {e(title)}">'
     f'<defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="hsl({hue} 45% 38%)"/>'
     f'<stop offset="1" stop-color="hsl({hue+22} 51% 12%)"/></linearGradient></defs>'
     '<rect width="680" height="280" rx="20" fill="url(#g)"/>'
     f'<circle cx="{95+seed%450}" cy="{80+(seed//13)%112}" r="{58+seed%54}" fill="#f5d08c" opacity=".12"/>'
     f'<path d="M68 203Q{200+seed%100} {45+seed%92} 350 147T612 115" stroke="#efd992" stroke-width="9" fill="none" opacity=".67"/>'
     f'<circle cx="{120+seed%420}" cy="{35+(seed//11)%170}" r="15" fill="#ffe8a8" opacity=".7"/></svg>')
    question=f"در بررسی «{title}» چه متغیرهایی باید کنترل شوند تا بتوان اثر مستقل مداخله یا عامل مورد مطالعه را ارزیابی کرد؟"
    hypothesis=f"فرضیه پژوهشی باید نشان دهد کدام ویژگی «{title}» با چه شاخص قابل اندازه‌گیری، در چه جمعیت یا شرایطی و در مقایسه با چه حالت مرجعی تغییر می‌کند."
    customized=details(title,card["id"])
    headings=[
      ("ماهیت تخصصی و جایگاه علمی",f"{title} از موضوعات حوزه «{group}» است. {theory} برای این موضوع لازم است مفهوم، دامنه جغرافیایی یا زیستی، نوع کاربری و محدودیت‌های استنتاج از ابتدا روشن شود."),
      ("پرسش پژوهشی و چارچوب نظری",f"{question} {hypothesis} {customized}"),
      ("روش تحقیق و طراحی ارزیابی",f"{design} در برنامه ویژه «{title}»، تعریف جامعه هدف، نمونه، معیار ورود و خروج، مدت پایش و شیوه تحلیل آماری از اجزای ضروری پروتکل است."),
      ("شاخص‌های سنجش و تحلیل داده",f"{metrics} انتخاب هر شاخص برای «{title}» باید به پرسش تحقیق مرتبط باشد و همراه با واحد اندازه‌گیری، روش آزمون، عدم‌قطعیت و محدوده معتبر گزارش شود."),
      ("عوامل مخدوش‌گر و کنترل کیفیت",f"{control} داده‌های «{title}» بدون ثبت متغیرهای همراه، کنترل نمونه و سنجش تکرارپذیری نمی‌توانند مبنای نتیجه قطعی یا ادعای عملکرد باشند."),
      ("امکان‌سنجی فنی، اقتصادی و مسئولیت‌پذیری",f"{decision} یافته‌های مربوط به «{title}» تا زمان سنجش مستقلی از اثربخشی و ریسک، به‌عنوان مسیر بررسی و نه محصول، خدمت یا نتیجه تأییدشده معرفی می‌شوند."),
    ]
    faq=[
       (f"برای ارزیابی علمی {title} از کجا باید شروع کرد؟",f"با تعریف مسئله، مرور منابع تخصصی، تعیین محدوده بررسی و انتخاب شاخص‌هایی که در حوزه {group} قابل سنجش و تکرار باشند."),
       (f"چه شواهدی برای تصمیم‌گیری درباره {title} کافی است؟", "شواهد متناسب با ادعا شامل داده قابل ردیابی، روش آزمون روشن، تکرار کافی، کنترل متغیرهای مخدوش‌گر و ارزیابی مستقل نتایج است."),
       (f"آیا زمرد ملل خدمت یا محصول مرتبط با {title} ارائه می‌کند؟", "این صفحه معرفی علمی یک حوزه موضوعی است. وجود عنوان به‌معنای عرضه عملیاتی، موجودی محصول، مجوز یا نتیجه پژوهشی تأییدشده نیست؛ اطلاعات خدمات باید جداگانه استعلام و مستند شود."),
    ]
    blocks="".join(f'<section class="topic-panel"><h2>{e(t)}</h2><p>{e(v)}</p></section>' for t,v in headings)
    faqs="".join(f'<details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q,a in faq)
    nav="<a href='/'>خانه</a><a href='/topics/'>دانشنامه تخصصی</a><a href='/research/'>مرکز تحقیقات</a><a href='/company/'>درباره شرکت</a>"
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{tag}</title><meta name="description" content="{e(desc)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="{e(canon)}">
<meta property="og:type" content="article"><meta property="og:site_name" content="زمرد ملل">
<meta property="og:locale" content="fa_IR"><meta property="og:title" content="{tag}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canon)}"><meta property="og:image" content="{e(graphic)}">
<meta name="twitter:card" content="summary"><meta name="twitter:title" content="{tag}">
<meta name="twitter:description" content="{e(desc)}">
<script type="application/ld+json">{schema}</script>
<style>
:root{{--bg:#102d23;--gold:#f0d08b;--paper:#f7edd9}}*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}body{{margin:0;background:radial-gradient(ellipse at 80% 2%,#2b533e,#102d23 45%);color:var(--paper);font-family:Tahoma,Arial,sans-serif;line-height:2}}
header,main,footer{{width:min(1130px,calc(100% - 34px));margin:auto}}
header{{padding:22px 0;border-bottom:1px solid #b19e6c82;display:flex;gap:15px;flex-wrap:wrap}}
header a,footer a,.topic-links a{{color:var(--gold);text-decoration:none}}
a:hover{{text-decoration:underline}}a:focus-visible,summary:focus-visible{{outline:3px solid #fff;outline-offset:5px}}
main{{padding:26px 0 60px}}h1{{font-size:clamp(27px,4vw,49px);line-height:1.4;color:var(--gold)}}h2{{color:var(--gold);line-height:1.55;font-size:clamp(20px,2vw,26px);margin:0 0 13px}}
.topic-lead{{font-size:clamp(17px,1.5vw,21px);max-width:90ch}}
.topic-hero{{display:grid;grid-template-columns:minmax(0,1fr) minmax(200px,.75fr);gap:18px;align-items:center}}
.topic-hero svg{{width:100%;height:auto;border:1px solid #c6a77870;border-radius:18px}}
.topic-panel,details{{padding:21px 24px;border:1px solid #a99a7179;background:#18382bdb;border-radius:18px;margin:17px 0;box-shadow:0 9px 30px #0002}}
.topic-panel p,details p{{margin:0;max-width:100ch}}summary{{cursor:pointer;color:var(--gold);font-weight:bold;font-size:17px}}
.topic-links{{display:flex;flex-wrap:wrap;gap:15px;padding:20px 0}}.disclaimer{{border-right:4px solid #e4ca89;padding:15px 19px;background:#254632;font-size:14px}}
footer{{padding:23px 0 44px;border-top:1px solid #b19e6c82;color:#dfd2ae}}
@media(max-width:650px){{.topic-hero{{grid-template-columns:1fr}}.topic-panel,details{{padding:17px}}}}
</style></head><body data-zm-dedicated-topic="{e(card["id"])}">
<header><strong>شرکت کشت و صنعت زمرد ملل</strong>{nav}</header>
<main class="zm-topic-article">
<div class="topic-hero"><div><p><a href="/topics/">موضوعات تخصصی</a> / {e(group)}</p>
<h1>{e(title)}</h1><p class="topic-lead">معرفی علمی و ارزیابی پژوهشی «{e(title)}» در حوزه {e(group)}؛ از مبانی نظری و روش تحقیق تا شاخص‌های عملکرد، محدودیت‌های فنی و امکان‌سنجی کاربرد.</p></div>
{visual}</div>
{blocks}
<section class="topic-panel"><h2>پرسش‌های کلیدی</h2>{faqs}</section>
<section class="topic-panel"><h2>منابع، مطالعه تکمیلی و پیوندهای مرتبط</h2>
<p>برای ادامه مطالعه، منابع علمی داوری‌شده و دستورالعمل‌های معتبر ویژه این رشته باید با توجه به پرسش مشخص پژوهش انتخاب شوند. اطلاعات و نتایج منتشرشده در منابع بیرونی به‌تنهایی نشان‌دهنده انجام پروژه در شرکت نیستند.</p>
<nav class="topic-links"><a href="/topics/">فهرست موضوعات تخصصی</a>
<a href="{e(row.get("sectorPath") or "/research/")}">حوزه اصلی: {e(group)}</a>
<a href="/research/">مأموریت پژوهشی زمرد ملل</a>{origlink}</nav></section>
<p class="disclaimer">این متن، شناسنامه موضوعی و راهنمای آشنایی علمی است؛ ادعای اجرای آزمایش مشخص، اخذ تأییدیه، داشتن تجهیزات آزمایشگاهی یا تضمین نتایج اقتصادی نیست. برای خدمات واقعی و همکاری‌های تحقیقاتی، شرایط و صلاحیت‌ها باید جداگانه احراز شوند.</p></main>
<footer>زمرد ملل · اطلاعات علمی و پژوهشی · <a href="/about/">درباره ما</a></footer>
<!-- {VERSION}:topic --></body></html>'''

def index_page(group_map, counts):
    panels=[]
    for row,cards in group_map:
        rid=row["id"]
        links="".join(f'<li><a href="{e(c["canonicalUrl"])}">{e(c["title"])}</a></li>' for c in cards)
        panels.append(f'<section id="{rid.lower()}"><h2>{e(row["title"])}</h2><p>{e(row.get("description",""))}</p><ul>{links}</ul></section>')
    body="\n".join(panels)
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>دانشنامه تخصصی زمرد ملل | ۶۰۵ موضوع علمی، فنی و پژوهشی</title>
<meta name="description" content="فهرست حوزه‌های تخصصی زمرد ملل شامل علوم کشاورزی، ژنتیک، آزمایشگاه‌ها، مراکز تحقیقات، صنعت، فناوری و خدمات؛ دسترسی مستقیم به صفحات معرفی هر موضوع.">
<meta name="robots" content="index,follow"><link rel="canonical" href="{BASE}/topics/">
<meta property="og:type" content="website"><meta property="og:title" content="دانشنامه تخصصی زمرد ملل"><meta property="og:url" content="{BASE}/topics/">
<style>
body{{background:#102d23;color:#f8eed9;font-family:Tahoma,Arial,sans-serif;line-height:1.95;margin:0}}
main,header,footer{{max-width:1280px;width:calc(100% - 35px);margin:auto}}header,footer{{padding:20px 0}}
h1,h2{{color:#f2d18b}}section{{border:1px solid #b99a6580;border-radius:17px;padding:20px;margin:20px 0;background:#1a392b}}
section ul{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;list-style:none;padding:0}}
section li a{{display:block;padding:12px;border:1px solid #a99b6870;border-radius:12px;color:#f7d99f;text-decoration:none}}
a:focus-visible{{outline:3px solid #fff}}a:hover{{text-decoration:underline}}
</style></head><body><header><a href="/" style="color:#f2d18b">صفحه اصلی زمرد ملل</a> · <a href="/research/" style="color:#f2d18b">مرکز تحقیقات</a></header>
<main><h1>دانشنامه حوزه‌های تخصصی زمرد ملل</h1><p>این فهرست به معرفی رشته‌ها و موضوعات علمی، کشاورزی، صنعتی و خدماتی اختصاص دارد. معرفی موضوع به‌معنای اجرای طرح یا عرضه خدمت نیست؛ هر صفحه محدوده علمی و معیارهای بررسی تخصصی را توضیح می‌دهد.</p>
{body}<p><a href="/topics/sitemap.xml">نقشه سایت موضوعات تخصصی (XML)</a></p></main>
<footer>شرکت کشت و صنعت زمرد ملل · <a href="/about/">معرفی شرکت</a></footer></body></html>'''

def sitemap(urls):
    from xml.sax.saxutils import escape as xml_e
    body="".join(f'<url><loc>{xml_e(u)}</loc><lastmod>{PUBLISHED}</lastmod></url>' for u in urls)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+body+'</urlset>\n'

def build(source, homefile, output):
    if VERSION in source:raise ValueError("Already deployed")
    if 'zm-research-three-shelves-20261018' not in source or 'zm-v9-real-pages-unique-links-20261018' not in source:
        raise ValueError("Expected existing V9+three-shelves baseline")
    m=list(MANIFEST_RE.finditer(source))
    if len(m)!=1:raise ValueError('Unable to find unique data manifest')
    match=m[0]; conf=json.loads(match.group(2));rows=conf["rows"]
    if len(rows)!=29 or sum(len(r["cards"]) for r in rows)!=605:
        raise ValueError('Unexpected row/card count: refuse to modify')
    if [r["id"] for r in rows if r["index"]>26]!=["ZM-R27","ZM-R28","ZM-R29"]:
        raise ValueError('Unexpected newer research shelves')
    if sum(len(r["cards"]) for r in rows if r["index"]>26)!=60:
        raise ValueError('Research card count mismatch')
    for r in rows:
        if r["id"] not in FIELDS and r["index"]<=26:raise ValueError("Missing editorial framework")
        if not re.fullmatch(r'ZM-R\d{2}',r["id"]):raise ValueError('Invalid group id')
    newroot=output/"topics";newroot.mkdir(parents=True,exist_ok=False)
    # Existing /research/ is served statically only because it disables Passenger.
    # Apply the same route-local rule without touching the root cPanel configuration.
    (newroot/".htaccess").write_text("PassengerEnabled off\nDirectoryIndex index.html\nOptions -Indexes\n",encoding="ascii")
    existing_groups=[r for r in rows if r["index"]<=26]
    original_cards=[json.dumps(c,ensure_ascii=False,sort_keys=True) for r in existing_groups for c in r["cards"]]
    original_newresearch=[json.dumps(r,ensure_ascii=False,sort_keys=True) for r in rows if r["index"]>26]
    count=0;manifest=[];allpages=set();touched=[]
    for row in existing_groups:
        for card in row["cards"]:
            slug=card["slug"]
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,95}',slug):
                raise ValueError("Unsafe slug: "+str(slug))
            path=f"/topics/{row['id'].lower()}/{slug}/"
            if path in allpages: raise ValueError("Duplicate topic path")
            allpages.add(path)
            prev=card.get("canonicalUrl")
            page=topic_page(card,row,prev)
            target=newroot/row["id"].lower()/slug/"index.html"
            target.parent.mkdir(parents=True,exist_ok=False)
            target.write_text(page,encoding='utf-8')
            card["previousCanonicalUrl"]=prev
            card["canonicalUrl"]=path
            card["livePage"]=True
            manifest.append((row["id"],card["id"],card["title"],path,prev))
            count+=1
    if count!=545:raise ValueError("Expected 545 old-row cards")
    if [json.dumps(r,ensure_ascii=False,sort_keys=True) for r in rows if r["index"]>26]!=original_newresearch:
        raise ValueError("Original research cards altered")
    # Only destination metadata of previous 545 cards may differ.
    for r in existing_groups:
        for c in r["cards"]:
            assert c["previousCanonicalUrl"] is None or isinstance(c["previousCanonicalUrl"],str)
    allurls=[BASE+card["canonicalUrl"] for r in rows for card in r["cards"]]
    if len(allurls)!=605 or len(set(allurls))!=605:raise ValueError("Invalid one-to-one URLs")
    (newroot/"index.html").write_text(index_page([(r,r["cards"]) for r in rows],count),encoding='utf-8')
    (newroot/"sitemap.xml").write_text(sitemap([BASE+"/topics/"]+allurls),encoding='utf-8')
    (newroot/"topic-manifest.json").write_text(json.dumps(
       {"version":VERSION,"pageCount":605,"newPages":545,"existingResearchPages":60,
        "topics":[dict(row=a,id=b,title=c,path=d,priorPage=e) for a,b,c,d,e in manifest]},
       ensure_ascii=False,indent=2),encoding='utf-8')
    conf["version"]="homepage-605-unique-topic-links"
    conf["topicPageCount"]=605
    updated=source[:match.start(2)]+json.dumps(conf,ensure_ascii=False,separators=(",",":"))+source[match.end(2):]
    # Add a permanent, crawlable, user-facing directory link to existing footer.
    last=updated.rfind("</footer>")
    if last<0:raise ValueError("Missing site footer")
    foot='<p class="zm-full-topics-index-link"><a href="/topics/">دانشنامه تخصصی زمرد ملل؛ معرفی همه حوزه‌های علمی و فنی</a></p>'
    updated=updated[:last]+foot+updated[last:]
    updated=updated.replace("</body>",f"<!-- {VERSION} --></body>",1)
    if homefile.exists() or not updated.rstrip().endswith("</html>"):
        raise ValueError("Output path exists or document broken")
    homefile.write_text(updated,encoding="utf-8")
    # Strong identity guard; no pages or card count removed.
    check=json.loads(MANIFEST_RE.search(updated).group(2))
    assert len(check["rows"])==29 and sum(len(x["cards"]) for x in check["rows"])==605
    assert [c["id"] for r in check["rows"] for c in r["cards"]] == [c["id"] for r in rows for c in r["cards"]]
    assert len(list(newroot.rglob("index.html")))==546
    assert len(list(newroot.glob("zm-r*")))==26
    assert updated.count(VERSION)==1
    assert updated.count('class="zm-full-topics-index-link"')==1
    assert len(set(allurls))==605
    assert all('data-zm-dedicated-topic' in p.read_text(encoding='utf-8') for p in list(newroot.rglob('index.html'))[1:15] if p.parent.name!='topics')
    print("TOPIC_ARTICLE_DOCUMENTS=545")
    print("RETAINED_RESEARCH_ARTICLES=60")
    print("TOTAL_UNIQUE_CARD_DESTINATIONS=605")
    print("TOPIC_SEO_TITLE_META_CANONICAL_OG_JSONLD=yes")
    print("ORIGINAL_ROWS_IMAGES_TITLES_IDS_ORDER=preserved")

def main():
    a=argparse.ArgumentParser()
    a.add_argument("live_home",type=Path)
    a.add_argument("--output",type=Path,required=True)
    a.add_argument("--stage-root",type=Path,required=True)
    opt=a.parse_args()
    if opt.output.exists() or opt.stage_root.exists():
        raise ValueError("Refuse nonempty outputs")
    opt.stage_root.mkdir(parents=True)
    try:
        build(opt.live_home.read_text(encoding="utf-8"),opt.output,opt.stage_root)
    except BaseException:
        import shutil
        shutil.rmtree(opt.stage_root)
        raise
if __name__=="__main__":main()
