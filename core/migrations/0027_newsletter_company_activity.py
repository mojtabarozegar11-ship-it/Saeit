from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0026_companyinquiry")]

    operations = [
        migrations.AddField(model_name="newslettersubmission", name="company_unit_title", field=models.CharField(blank=True, help_text="واحد/مرکز تخصصی که این خبر باید برای آن پرونده بسازد.", max_length=300)),
        migrations.AddField(model_name="newslettersubmission", name="company_unit_slug", field=models.SlugField(blank=True, help_text="شناسه پایدار واحد؛ در صورت خالی بودن توسط سیستم ساخته می‌شود.", max_length=180)),
        migrations.AddField(model_name="newslettersubmission", name="company_activity_status", field=models.CharField(blank=True, default="پژوهش", help_text="پژوهش، مطالعه، طراحی، پایلوت، تولید یا آینده.", max_length=40)),
        migrations.AddField(model_name="newslettersubmission", name="company_project_title", field=models.CharField(blank=True, help_text="نام پروژه مادر مرتبط.", max_length=300)),
        migrations.AddField(model_name="newsletterstory", name="company_unit_title", field=models.CharField(blank=True, help_text="نام واحد/مرکز تخصصی مرتبط با این خبر؛ فقط عنوان سازمانی ثبت‌شده.", max_length=300)),
        migrations.AddField(model_name="newsletterstory", name="company_unit_slug", field=models.SlugField(blank=True, help_text="شناسه پایدار پرونده واحد تخصصی شرکت.", max_length=180)),
        migrations.AddField(model_name="newsletterstory", name="company_activity_status", field=models.CharField(blank=True, default="", help_text="وضعیت فعالیت: پژوهش، مطالعه، طراحی، پایلوت، تولید یا آینده.", max_length=40)),
        migrations.AddField(model_name="newsletterstory", name="company_project_title", field=models.CharField(blank=True, help_text="پروژه مادر مرتبط، در صورت ثبت.", max_length=300)),
        migrations.AddField(model_name="newsletterstory", name="company_activity_content", field=models.TextField(blank=True, help_text="متن ساختاریافته پرونده فعالیت شرکت.")),
    ]
