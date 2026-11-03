from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("company_messaging", "0001_initial")]
    operations = [
        migrations.AddField(model_name="contact", name="bale_chat_id",
                            field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="contact", name="eitaa_chat_id",
                            field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="contact", name="rubika_chat_id",
                            field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="contact", name="bale_consent_at",
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="contact", name="eitaa_consent_at",
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="contact", name="rubika_consent_at",
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AlterField(model_name="message", name="channel",
            field=models.CharField(max_length=12, choices=[
                ("internal", "داخلی"), ("email", "ایمیل"), ("sms", "پیامک"),
                ("telegram", "تلگرام"), ("bale", "بله"), ("eitaa", "ایتا"),
                ("rubika", "روبیکا"), ("whatsapp", "واتساپ"),
            ])),
    ]
