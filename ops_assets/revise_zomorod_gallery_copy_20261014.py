#!/usr/bin/env python3
# Dedicated editor-only update of six existing Zomorod Melal gallery reports.
# No photo replacement, schema changes, migrations, or changes to other pages.
import json,os,sys,hashlib,tempfile,html,shutil,argparse
from pathlib import Path
ROOT=Path("/home/zomorod2/Saeit")
STAGE=Path("/home/zomorod2/Saeit-staging/gallery_publish_20261014")
PART=ROOT/"templates/modern/partials/zomorod_gallery_20261014.html"
REPORT=ROOT/"templates/modern/zomorod_report_20261014.html"
PHOTO_TAG="ZOMOROD_GALLERY_20261014"
DATA=json.loads(r'''[{"slug":"gallery-digital-management","title":"مدیریت یکپارچه و تحول دیجیتال در شرکت زمرد ملل","summary":"زمرد ملل با رویکرد مدیریت یکپارچه، برنامه‌ریزی پروژه، پایش عملکرد و توسعه ابزارهای دیجیتال، حوزه‌های کشاورزی، صنعت، پژوهش و تجارت را در یک ساختار هماهنگ معرفی می‌کند.","links":["https://zomorodmelal.ir/company/","https://zomorodmelal.ir/agents/"],"body":"شرکت کشت و صنعت زمرد ملل به مدیریت مجتبی روزگار، مجموعه‌ای با حوزه‌های تخصصی در کشاورزی، صنعت، خدمات، پژوهش و توسعه بازار است. یکی از محورهای راهبردی شرکت، هماهنگ‌سازی این فعالیت‌ها در یک چارچوب مدیریتی قابل ارزیابی است؛ چارچوبی که در آن هر ایده از مرحله تعریف مسئله و امکان‌سنجی تا طراحی، تأمین منابع، اجرا و سنجش نتیجه، مسیر مشخصی داشته باشد.\n\nمدیریت یکپارچه در زمرد ملل به معنای اتصال تصمیم‌های تولیدی به تحلیل اقتصادی، برنامه زمانی، تأمین، مدیریت ریسک و نیاز بازار است. برای مثال، تصمیم درباره توسعه یک باغ، احداث گلخانه یا راه‌اندازی خط فرآوری بدون بررسی منابع آب، سرمایه اولیه، هزینه‌های جاری، ظرفیت فروش و الزامات قانونی، تصمیمی کامل نیست. رویکرد شرکت بر بررسی این مؤلفه‌ها پیش از تعهد اجرایی استوار است.\n\nتحول دیجیتال و سامانه‌های هوشمند نیز در سبد حوزه‌های کاری شرکت جایگاه دارند. وب‌سایت زمرد ملل به‌عنوان یک درگاه معرفی خدمات، دانش تخصصی، فرصت‌های همکاری و ارتباط با مخاطبان توسعه می‌یابد. ابزارهای داده‌محور، گزارش‌های مدیریتی، اتوماسیون فرایندها و هوش مصنوعی می‌توانند برای سازمان‌دهی اطلاعات و پشتیبانی از تصمیم‌ها به کار گرفته شوند؛ البته قابلیت هر ابزار و وضعیت اجرای آن باید به‌صورت مستقل ارزیابی شود.\n\nدر این الگو، اولویت با شفافیت مسئولیت‌ها و قابلیت سنجش نتایج است: تعریف هدف، تعیین مسئول، برآورد منابع، کنترل هزینه، مدیریت کیفیت و تهیه گزارش مستند. توسعه سامانه تنها زمانی ارزشمند است که به حل مسئله واقعی، کاهش دوباره‌کاری، افزایش سرعت پاسخ‌گویی یا بهبود کیفیت تصمیم کمک کند.\n\nزمرد ملل از صاحبان طرح، تولیدکنندگان، پژوهشگران، تأمین‌کنندگان و همکاران تخصصی دعوت می‌کند نیاز خود را با شرح هدف، منابع موجود و خروجی مورد انتظار مطرح کنند. درباره دامنه خدمات، شرایط همکاری و مرحله اجرایی هر طرح پس از بررسی موردی تصمیم‌گیری می‌شود.","old_title":"مدیریت دیجیتال و برنامه‌ریزی در زمرد ملل"},{"slug":"gallery-growth-presentation","title":"اقتصاد کشاورزی، امکان‌سنجی و برنامه‌ریزی توسعه در زمرد ملل","summary":"ارزیابی اقتصادی طرح‌های کشاورزی و صنعتی، مدیریت هزینه، تحلیل بازار و برنامه‌ریزی توسعه از موضوعات محوری در رویکرد تصمیم‌گیری شرکت کشت و صنعت زمرد ملل است.","links":["https://zomorodmelal.ir/company/","https://zomorodmelal.ir/research/","https://zomorodmelal.ir/economy/"],"body":"توسعه پایدار یک کسب‌وکار کشاورزی یا صنعتی فقط با افزایش ظرفیت تولید حاصل نمی‌شود؛ سرمایه‌گذاری باید از منظر منابع، هزینه، تقاضا، ریسک و توان اجرا بررسی شود. شرکت کشت و صنعت زمرد ملل، اقتصاد کشاورزی و ارزیابی مالی طرح‌ها را بخشی از منطق برنامه‌ریزی حوزه‌های فعالیت خود معرفی می‌کند.\n\nدر امکان‌سنجی یک طرح، نقطه آغاز تعریف دقیق محصول یا خدمت، بازار هدف و محدودیت‌های واقعی است. سپس هزینه زمین و زیرساخت، تجهیزات، سرمایه در گردش، نیروی انسانی، مصرف آب و انرژی، هزینه‌های حمل و نگهداری و مراحل اخذ مجوز در کنار ظرفیت تولید و سناریوهای فروش بررسی می‌شوند. جداکردن درآمد پیش‌بینی‌شده از درآمد تحقق‌یافته و لحاظ‌کردن عدم قطعیت، شرط تهیه تحلیل معتبر است.\n\nدر زنجیره کشاورزی، تصمیم اقتصادی به مراحل کاشت و داشت محدود نیست. انتخاب رقم و نهاده، مکانیزاسیون، مدیریت ضایعات، نگهداری پس از برداشت، فرآوری و بسته‌بندی می‌توانند بر بهای تمام‌شده و قدرت رقابت محصول اثر بگذارند. برای سنجش نتیجه، شاخص‌هایی مانند هزینه واحد محصول، بهره‌وری آب، نقطه سربه‌سر، جریان نقدی و حساسیت به تغییر قیمت‌ها باید با داده قابل اتکا محاسبه شوند.\n\nبخش پژوهش و توسعه شرکت به مطالعه مسائل تخصصی، تحلیل داده و تدوین خروجی‌های قابل بررسی می‌پردازد. هدف آن است که تصمیم توسعه به جای اتکا به وعده‌های کلی، به فرض‌های شفاف، منابع مستند، سناریوهای مقایسه‌پذیر و معیارهای پذیرش متکی باشد.\n\nزمرد ملل زمینه گفت‌وگو درباره طرح‌های کشاورزی، صنعتی، فرآوری و تجارت را فراهم می‌کند. معرفی این حوزه‌ها به معنای تضمین سود یا تصویب سرمایه‌گذاری نیست؛ هر فرصت باید با اطلاعات پروژه، بررسی ریسک و توافق روشن میان طرف‌های ذی‌ربط ارزیابی شود.","old_title":"ارائه شاخص‌های رشد و توسعه در نشست مدیریتی"},{"slug":"gallery-smart-agriculture","title":"کشاورزی هوشمند و مدیریت زنجیره تولید؛ محور تخصصی زمرد ملل","summary":"زمرد ملل حوزه‌هایی مانند تولیدات گیاهی و باغی، دام و طیور، آبزی‌پروری، مدیریت آب و خاک، مکانیزاسیون و کشاورزی دقیق را در زنجیره خدمات و توسعه کشاورزی معرفی می‌کند.","links":["https://zomorodmelal.ir/agriculture/","https://zomorodmelal.ir/agents/"],"body":"کشاورزی یکی از ارکان تخصصی شرکت کشت و صنعت زمرد ملل است. حوزه‌های معرفی‌شده در این بخش از زراعت، باغداری، گلخانه و نهالستان تا دامپروری، طیور، زنبورداری، آبزی‌پروری و خدمات فنی و پشتیبان تولید امتداد دارند. نگاه شرکت، بررسی پیوند میان منابع طبیعی، فناوری، مدیریت عملیات و بازار در کل زنجیره تولید است.\n\nبرای آغاز یک طرح کشاورزی، شناخت شرایط واقعی مزرعه ضروری است: اقلیم، وضعیت خاک، دسترسی و کیفیت آب، الگوی کشت، امکانات مکانیزاسیون و سابقه تولید. انتخاب فناوری بدون این اطلاعات ممکن است هزینه ایجاد کند بی‌آنکه عملکرد یا پایداری را بهبود دهد. ازاین‌رو در طراحی و بررسی پروژه‌ها، ثبت داده پایه و تعریف هدف قابل سنجش اهمیت ویژه‌ای دارد.\n\nکشاورزی هوشمند شامل ابزارهایی برای پایش آبیاری، مصرف نهاده، وضعیت رشد محصول، آفات و بیماری‌ها و عملکرد تولید است. سنجش از دور، حسگرها، داده‌های اقلیمی و مدل‌های تحلیلی می‌توانند به مدیر مزرعه برای تشخیص مسئله و مقایسه گزینه‌ها کمک کنند. این ابزارها باید با دانش تخصصی کشاورزی و اعتبارسنجی میدانی همراه باشند و جایگزین بررسی کارشناسی در محل نیستند.\n\nزنجیره ارزش کشاورزی پس از برداشت نیز ادامه دارد. سورتینگ، نگهداری، سردخانه، فرآوری، بسته‌بندی، استانداردسازی و توسعه بازار از حوزه‌هایی هستند که می‌توانند به کاهش ضایعات و افزایش ارزش افزوده کمک کنند. هم‌زمان، حفاظت خاک، بهره‌وری مصرف آب، مدیریت پسماند و رعایت الزامات بهداشتی و محیط‌زیستی باید در طراحی طرح‌ها دیده شوند.\n\nزمرد ملل مسیر ارتباط تولیدکنندگان، بهره‌برداران، پژوهشگران، تأمین‌کنندگان و متقاضیان خدمات تخصصی را در درگاه خود معرفی می‌کند. نوع همکاری و مرحله اجرای هر پروژه بر اساس نیاز واقعی، شرایط فنی، امکان‌سنجی و توافق مشخص می‌شود.","old_title":"گفت‌وگوی مدیریتی درباره کشاورزی هوشمند"},{"slug":"gallery-business-collaboration","title":"همکاری‌های تجاری، شبکه تأمین و توسعه بازار در شرکت زمرد ملل","summary":"زمرد ملل برای همکاری با تولیدکنندگان، تأمین‌کنندگان، متخصصان، سرمایه‌گذاران و شرکای تجاری، حوزه‌های تأمین، فروش، بازاریابی، فرآوری و توسعه بازار را معرفی می‌کند.","links":["https://zomorodmelal.ir/company/","https://zomorodmelal.ir/market/","https://zomorodmelal.ir/industry/"],"body":"یکی از جهت‌گیری‌های شرکت کشت و صنعت زمرد ملل، توسعه ارتباط میان تولید، خدمات تخصصی و بازار است. در این ساختار، فرصت همکاری می‌تواند از تأمین نهاده و تجهیزات کشاورزی تا مشارکت در توسعه محصول، فرآوری، بسته‌بندی، بازاریابی، خدمات فنی، پژوهش و فروش را دربرگیرد.\n\nدر حوزه کشاورزی و صنعت، وجود شبکه تأمین قابل اتکا برای کیفیت و تداوم فعالیت اهمیت دارد. انتخاب تأمین‌کننده صرفاً بر اساس قیمت اولیه کافی نیست؛ مشخصات فنی، استاندارد، قابلیت تحویل، خدمات پس از فروش، تعهدات قراردادی و هزینه کل تأمین نیز باید بررسی شوند. همین منطق در انتخاب همکار تولیدی، پیمانکار یا ارائه‌دهنده خدمات تخصصی کاربرد دارد.\n\nزمرد ملل در بخش تجاری خود حوزه‌هایی مانند معرفی محصول، سفارش، زنجیره توزیع، توسعه بازار، برند و تجارت مجاز داخلی و خارجی را مطرح می‌کند. برای هر محصول، تعیین بازار هدف، مزیت رقابتی، ضوابط قانونی، شرایط حمل و تسویه، کنترل کیفیت و توان پاسخ‌گویی به مشتری از پیش‌نیازهای یک همکاری پایدار است.\n\nفرصت‌های همکاری در قالب‌های مختلف قابل بررسی‌اند: مشارکت پروژه‌ای، همکاری سازمانی، تأمین کالا و خدمات، فروشندگی، بازاریابی، نمایندگی یا مشاوره تخصصی. پذیرش هر همکاری وابسته به شناخت متقابل، بررسی مدارک و توانمندی‌ها و توافق روشن درباره دامنه کار، زمان‌بندی، هزینه و مسئولیت‌هاست.\n\nهدف از این رویکرد، شکل‌گیری روابط تجاری شفاف و ارزش‌آفرین است؛ روابطی که در آن نیاز واقعی طرفین مشخص باشد و نتیجه با شاخص‌هایی مانند کیفیت تحویل، رضایت مشتری، هزینه، زمان و پایداری همکاری سنجیده شود. علاقه‌مندان می‌توانند موضوع همکاری و پیشنهاد خود را از مسیر ارتباطی رسمی شرکت ثبت کنند.","old_title":"تعامل حرفه‌ای و توسعه همکاری‌های سازمانی"},{"slug":"gallery-executive-portrait","title":"معرفی مدیریت و رویکرد علمی شرکت کشت و صنعت زمرد ملل","summary":"شرکت کشت و صنعت زمرد ملل به مدیریت مجتبی روزگار، توسعه فعالیت‌های کشاورزی، صنعتی، پژوهشی و تجاری را با تأکید بر دانش تخصصی، برنامه‌ریزی اقتصادی و همکاری سازمان‌یافته دنبال می‌کند.","links":["https://zomorodmelal.ir/company/","https://zomorodmelal.ir/research/"],"body":"شرکت کشت و صنعت زمرد ملل به مدیریت مجتبی روزگار، فعالیت‌ها و برنامه‌های تخصصی خود را در حوزه‌های کشاورزی، صنعت، پژوهش، دانش و فناوری، خدمات و بازار معرفی می‌کند. در نگاه مدیریتی شرکت، توسعه یک فعالیت اقتصادی زمانی معنا پیدا می‌کند که دانش تخصصی، امکانات اجرایی، منابع مالی و نیاز مخاطب در کنار یکدیگر بررسی شوند.\n\nیکی از اصول مورد تأکید در معرفی ساختار شرکت، حرکت از ایده به طرح قابل ارزیابی است. برای این منظور، موضوع پروژه و ذی‌نفعان آن باید روشن باشد؛ سپس روش مطالعه، محدودیت‌ها، منابع موردنیاز، مسئول اجرا، شاخص‌های کیفیت و شرایط تحویل مشخص شوند. این رویکرد به کاهش تصمیم‌های شتاب‌زده و افزایش قابلیت پاسخ‌گویی کمک می‌کند.\n\nساختار معرفی‌شده زمرد ملل بخش‌هایی مانند کشاورزی، صنعت و فرآوری، پژوهش و توسعه، فناوری و هوش مصنوعی، تجارت و بازار، رسانه و آموزش را در بر می‌گیرد. ارتباط این بخش‌ها می‌تواند زمینه‌ای برای پروژه‌های میان‌رشته‌ای فراهم کند؛ برای نمونه مسئله یک واحد تولیدی ممکن است هم‌زمان به بررسی فنی، تحلیل اقتصادی، طراحی فرایند و توسعه بازار نیاز داشته باشد.\n\nدر حوزه پژوهش، اعتبار منابع، ثبت شواهد و تمایز میان یافته علمی، تفسیر کارشناسی و پیشنهاد اجرایی اهمیت دارد. در حوزه کسب‌وکار نیز ارزیابی حقوقی، مدیریت هزینه و شناسایی ریسک باید در کنار نوآوری دیده شود. این اصول، مبنایی برای تعریف مسئولانه فرصت‌ها و برنامه‌های توسعه فراهم می‌کنند.\n\nدرگاه رسمی زمرد ملل برای معرفی حوزه‌های کاری، محتوای تخصصی، ارتباط با همکاران و بررسی پیشنهادهای همکاری ایجاد شده است. معرفی یک حوزه به معنای ادعای اجرای قطعی همه پروژه‌های آن نیست؛ اطلاعات اجرایی و دستاوردهای هر برنامه باید در پرونده مستقل و مستند همان برنامه اعلام شود.","old_title":"پرتره رسمی مدیریت در دفتر مرکزی"},{"slug":"gallery-organizational-leadership","title":"چشم‌انداز زمرد ملل؛ توسعه پایدار، فناوری و زنجیره‌های ارزش","summary":"چشم‌انداز زمرد ملل بر پیوند کشاورزی، صنعت، پژوهش، فناوری، آموزش و تجارت در زنجیره‌های ارزش قابل ارزیابی و توسعه مرحله‌ای مبتنی است.","links":["https://zomorodmelal.ir/company/","https://zomorodmelal.ir/industry/","https://zomorodmelal.ir/knowledge/"],"body":"چشم‌انداز شرکت کشت و صنعت زمرد ملل بر ایجاد پیوند میان ظرفیت‌های تولیدی، دانش تخصصی و فرصت‌های بازار استوار است. در این نگاه، کشاورزی، صنعت، پژوهش، فناوری، آموزش و تجارت واحدهایی جدا از هم نیستند؛ هر حوزه می‌تواند در شکل‌گیری یک زنجیره ارزش مؤثر باشد که از شناسایی نیاز آغاز می‌شود و به تولید محصول یا ارائه خدمت قابل ارزیابی می‌رسد.\n\nدر بخش کشاورزی، توجه به بهره‌وری منابع، تولید مسئولانه، مدیریت آب و خاک و کاهش ضایعات اهمیت دارد. در بخش صنعت، توسعه محصول، فرآوری، کنترل کیفیت، استانداردسازی و بهره‌وری فرایندها مطرح است. تلفیق این دو حوزه می‌تواند فرصت‌هایی برای فرآوری محصولات کشاورزی، توسعه بسته‌بندی، خدمات پشتیبان تولید و ایجاد ارزش افزوده فراهم کند.\n\nپژوهش و آموزش در این ساختار نقش زیربنایی دارند. نیازهای تولیدکننده یا فعال اقتصادی باید به پرسش قابل مطالعه تبدیل شوند و یافته‌ها، پس از بررسی اعتبار و محدودیت‌ها، به راهنما، ابزار تصمیم‌یار یا پیشنهاد اجرایی تبدیل شوند. رسانه، وبلاگ و دانشنامه شرکت نیز برای معرفی موضوعات تخصصی و تسهیل دسترسی به دانش کاربردی در نظر گرفته شده‌اند.\n\nفناوری اطلاعات و هوش مصنوعی از محورهای توسعه مورد توجه زمرد ملل هستند. مدیریت داده، پایش شاخص‌ها، خودکارسازی فرایندهای مناسب و ارتباط دیجیتال با مخاطبان، ظرفیت بهبود سرعت و کیفیت خدمات را دارند؛ اما پذیرش هر فناوری باید متناسب با مسئله، هزینه، امنیت، امکان اجرا و نتیجه آزمون انجام گیرد.\n\nزمرد ملل توسعه مرحله‌ای، همکاری حرفه‌ای و مستندسازی را مبنای حرکت به سوی اهداف خود معرفی می‌کند. تحقق هر برنامه وابسته به امکان‌سنجی فنی و اقتصادی، تأمین منابع، رعایت قوانین و توافق با شرکای ذی‌ربط است. اشخاص و مجموعه‌های علاقه‌مند می‌توانند حوزه پیشنهادی همکاری را همراه با نیاز و خروجی مورد انتظار برای بررسی ارائه کنند.","old_title":"رهبری سازمانی و چشم‌انداز توسعه زمرد ملل"}]''')
assert len(DATA)==6 and len({r["slug"] for r in DATA})==6
assert all(250<len(r["body"]) and len(r["summary"])<300 for r in DATA)
assert all(r["links"] and all(u.startswith("https://zomorodmelal.ir/") for u in r["links"]) for r in DATA)
os.chdir(ROOT)
sys.path.insert(0,str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django
django.setup()
from portal.models import Article, GalleryPhoto
from django.db import transaction
from django.test import Client
from django.core.management import call_command
from django.utils import timezone

def atomic_file(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix="."+path.name+".",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(temp,0o644)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def validate():
    if not PART.is_file() or not REPORT.is_file():raise RuntimeError("Expected gallery templates absent")
    a=PART.read_text("utf-8")
    b=REPORT.read_text("utf-8")
    if PHOTO_TAG not in a or PHOTO_TAG not in b or a.count("<style>")!=1:
        raise RuntimeError("Unexpected gallery template version")
    matches=[]
    for row in DATA:
        art=Article.objects.select_related("cover").filter(slug=row["slug"],category="gallery").first()
        if art is None or art.state!="published" or not art.cover_id or not art.cover.is_approved:
            raise RuntimeError("Published article/approved photo not found: "+row["slug"])
        if art.title not in (row["title"],row["old_title"]):
            raise RuntimeError("This report was independently edited; refusing overwrite: "+row["slug"])
        matches.append(art)
    if len({a.pk for a in matches})!=6:raise RuntimeError("Articles are not unique")
    print("EDITORIAL_PRECHECK_OK",len(matches))
    return matches,a,b

def updated_partial(original):
    rest="<style>"+original.split("<style>",1)[1]
    cards=[]
    for row in DATA:
        slug=html.escape(row["slug"],quote=True)
        title=html.escape(row["title"])
        summary=html.escape(row["summary"])
        cards.append('<article class="zmg-item"><a href="/company-gallery/report/'+slug+'/">'
          '<img src="/company-gallery/photo/'+slug+'/" alt="'+title+'" loading="lazy">'
          '<div class="zmg-copy"><h3>'+title+'</h3><p>'+summary+'</p>'
          '<span>آشنایی با فعالیت‌های شرکت ←</span></div></a></article>')
    prefix='''<!-- ZOMOROD_GALLERY_20261014: six areas of activity of Zomorod Melal -->
<section class="wrap section-space zmg-section" id="managerial-gallery-20261014" aria-label="معرفی حوزه‌های فعالیت شرکت زمرد ملل">
  <div class="section-heading"><div><span class="eyebrow">زمرد ملل / حوزه‌های فعالیت</span><h2>آشنایی با فعالیت‌ها و چشم‌انداز شرکت زمرد ملل</h2></div>
  <p>معرفی شش محور تخصصی شرکت: مدیریت هوشمند، اقتصاد و توسعه، کشاورزی، همکاری تجاری، راهبری علمی و چشم‌انداز پایدار. برای هر محور، شرح فعالیت‌های معرفی‌شده، خدمات قابل بررسی و زمینه‌های همکاری ارائه شده است.</p></div>
  <div class="zmg-grid">'''
    return (prefix+"".join(cards)+"</div>\n</section>\n"+rest).encode("utf-8")

def updated_report(original):
    orig="این تصویر برای معرفی بصری و هویت سازمانی منتشر شده است و به تنهایی سند وقوع رویداد، قرارداد، بازدید یا نتیجه اقتصادی نیست."
    new="این گزارش، حوزه‌های کاری و برنامه‌های معرفی‌شده شرکت را تشریح می‌کند. وضعیت اجرایی، نتایج و دستاوردهای هر پروژه باید در پرونده اختصاصی و مستند آن بررسی شود."
    if orig not in original and new not in original:raise RuntimeError("Report notice changed externally")
    text=original.replace(orig,new)
    text=text.replace("رسانه سازمانی / گزارش تصویری","معرفی شرکت / حوزه‌های تخصصی")
    if not text.startswith("<!-- ZOMOROD_GALLERY_20261014"):raise RuntimeError("Report template ownership marker missing")
    return text.encode("utf-8")

def snapshot(rows,original_partial,original_report):
    backup=STAGE/("editorial_copy_backup_"+timezone.now().strftime("%Y%m%dT%H%M%S%f"))
    backup.mkdir(mode=0o700,parents=True)
    old=[]
    for a in rows:
        old.append({"id":a.pk,"slug":a.slug,"title":a.title,"summary":a.summary,
                    "body":a.body,"sources":a.sources,"cover_title":a.cover.title})
    p=backup/"six_articles_before.json"
    p.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding="utf-8")
    os.chmod(p,0o600)
    for name,blob in [("gallery_template_before.html",original_partial.encode("utf-8")),("report_template_before.html",original_report.encode("utf-8"))]:
        p=backup/name;p.write_bytes(blob);os.chmod(p,0o600)
    print("BACKUP_READY",backup.name)
    return backup

def verify_pages():
    c=Client(HTTP_HOST="zomorodmelal.ir")
    response=c.get("/company-gallery/")
    if response.status_code!=200:raise RuntimeError("Gallery request failed")
    s=response.content.decode("utf-8")
    for row in DATA:
        if row["title"] not in s or row["slug"] not in s:
            raise RuntimeError("New gallery caption absent "+row["slug"])
        r=c.get("/company-gallery/report/"+row["slug"]+"/")
        if r.status_code!=200:raise RuntimeError("Report route failed "+row["slug"])
        htmlbody=r.content.decode("utf-8")
        if row["title"] not in htmlbody or row["summary"] not in htmlbody:
            raise RuntimeError("Published report did not render updated copy "+row["slug"])
        if row["body"].split("\n\n",1)[0] not in htmlbody:
            raise RuntimeError("Report article body not showing current version "+row["slug"])
        # Never close a streamed FileResponse while inside SQLite atomic().
        # Django request_finished would close the transaction connection.
        # Approved photos and source files are unchanged by this editorial operation.
        print("COPY_AND_REPORT_OK",row["slug"])
    print("SIX_COMPANY_REPORTS_UPDATED_RENDER_OK")

def run(apply):
    records,partial,report=validate()
    candidate_partial=updated_partial(partial)
    candidate_report=updated_report(report)
    if not apply:
        print("COPY_DRAFT_READY",len(DATA), "NO_CHANGES")
        return
    snapshot(records,partial,report)
    touched=False
    try:
        with transaction.atomic():
            for row,art in zip(DATA,records):
                art.title=row["title"]
                art.summary=row["summary"]
                art.body=row["body"]
                art.sources=list(dict.fromkeys(row["links"]+["https://zomorodmelal.ir/company-gallery/photo/"+row["slug"]+"/"]))
                art.full_clean()
                art.save(update_fields=["title","summary","body","sources"])
                photo=art.cover
                photo.title=row["title"]
                photo.save(update_fields=["title"])
            atomic_file(PART,candidate_partial)
            touched=True
            atomic_file(REPORT,candidate_report)
            call_command("check",verbosity=0)
            verify_pages()
    except Exception:
        if touched:
            atomic_file(PART,partial.encode("utf-8"))
            atomic_file(REPORT,report.encode("utf-8"))
        print("EDITORIAL_CHANGE_ROLLED_BACK")
        raise
    import time
    wsgi=ROOT/"passenger_wsgi.py"
    if wsgi.exists():os.utime(wsgi,None)
    print("EDITORIAL_UPDATE_SUCCESS reports=6 gallery=1 photos_unchanged=6")
    for row in DATA:
        print("UPDATED_REPORT_URL=https://zomorodmelal.ir/company-gallery/report/"+row["slug"]+"/")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    g=parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight",action="store_true")
    g.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    try:run(args.apply)
    except Exception as err:
        print("EDITORIAL_UPDATE_FAILED",type(err).__name__,str(err)[:350],file=sys.stderr)
        sys.exit(1)
