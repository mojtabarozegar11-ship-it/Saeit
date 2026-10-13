from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0041_platformpageblock"),
    ]

    operations = [
        migrations.AlterField(
            model_name="platformpagecontent",
            name="page_key",
            field=models.CharField(
                choices=[
                    ("about", "درباره ما"),
                    ("agriculture", "کشاورزی"),
                    ("agents", "خدمات هوشمند"),
                    ("company", "معرفی شرکت"),
                    ("contact", "تماس با ما"),
                    ("economy", "اقتصاد"),
                    ("industry", "صنعت"),
                    ("knowledge", "دانشنامه"),
                    ("market", "بازار"),
                    ("research", "پژوهش"),
                    ("studio", "استودیو"),
                ],
                max_length=30,
                unique=True,
            ),
        ),
    ]
