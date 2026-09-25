from django.db import migrations


OCCASIONS = [
    ("nowruz", "نوروز", "iranian", "annual:farvardin-01", "نوروز و آغاز سال نو را تبریک می‌گوییم."),
    ("islamic-republic-day", "روز جمهوری اسلامی ایران", "iranian", "annual:farvardin-12", "فرارسیدن روز جمهوری اسلامی ایران گرامی باد."),
    ("teachers-day", "روز معلم", "iranian", "annual:ordibehesht-12", "روز معلم را به جامعه فرهیخته آموزش و پژوهش تبریک می‌گوییم."),
    ("ramadan", "ماه مبارک رمضان", "shia", "lunar:ramadan-01", "فرارسیدن ماه مبارک رمضان، ماه رحمت و خودسازی، گرامی باد."),
    ("eid-fitr", "عید سعید فطر", "shia", "lunar:shawwal-01", "عید سعید فطر مبارک باد."),
    ("ghadir", "عید سعید غدیر خم", "shia", "lunar:dhu-al-hijjah-18", "عید سعید غدیر خم مبارک باد."),
    ("ashura", "عاشورای حسینی", "shia", "lunar:muharram-10", "فرارسیدن تاسوعا و عاشورای حسینی را تسلیت می‌گوییم."),
    ("arbaeen", "اربعین حسینی", "shia", "lunar:safar-20", "اربعین حسینی را تسلیت می‌گوییم."),
    ("prophet-birthday", "میلاد پیامبر اکرم و امام صادق", "shia", "lunar:rabi-al-awwal-17", "میلاد پیامبر اکرم و امام جعفر صادق مبارک باد."),
    ("imam-ali-birthday", "ولادت حضرت امیرالمؤمنین و روز پدر", "shia", "lunar:rajab-13", "ولادت حضرت امیرالمؤمنین و روز پدر مبارک باد."),
    ("imam-hossein-birthday", "ولادت امام حسین و روز پاسدار", "shia", "lunar:shaban-03", "ولادت امام حسین و روز پاسدار مبارک باد."),
    ("imam-mahdi-birthday", "ولادت حضرت مهدی موعود", "shia", "lunar:shaban-15", "ولادت حضرت مهدی موعود مبارک باد."),
    ("company-anniversary", "سالروز آغاز فعالیت شرکت", "company", "annual:aban-25", "سالروز آغاز فعالیت شرکت کشت و صنعت زمرد ملل گرامی باد."),
]


def seed(apps, schema_editor):
    Occasion = apps.get_model("core", "NewsletterOccasion")
    for code, title, kind, rule, template in OCCASIONS:
        Occasion.objects.update_or_create(
            code=code,
            defaults={
                "title": title,
                "kind": kind,
                "date_rule": rule,
                "message_template": template,
                "active": True,
                "requires_owner_approval": True,
            },
        )


def unseed(apps, schema_editor):
    Occasion = apps.get_model("core", "NewsletterOccasion")
    Occasion.objects.filter(code__in=[x[0] for x in OCCASIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0022_newsletteroccasion_and_more")]
    operations = [migrations.RunPython(seed, unseed)]
