from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="Agent",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("code",models.SlugField(unique=True)),("name",models.CharField(max_length=200)),("mission",models.TextField()),
            ("risk_level",models.CharField(default="low",max_length=10)),("active",models.BooleanField(default=False))]),
        migrations.CreateModel(name="KnowledgeArticle",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("title",models.CharField(max_length=300)),("slug",models.SlugField(unique=True)),("content",models.TextField()),
            ("version",models.PositiveIntegerField(default=1)),("published",models.BooleanField(default=False))]),
        migrations.CreateModel(name="Product",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("title",models.CharField(max_length=300)),("product_type",models.CharField(max_length=50)),
            ("price",models.DecimalField(decimal_places=2,default=0,max_digits=14)),("currency",models.CharField(default="IRR",max_length=10)),
            ("active",models.BooleanField(default=False)),("metadata",models.JSONField(default=dict))]),
        migrations.CreateModel(name="ResearchProject",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),
            ("title",models.CharField(max_length=300)),("objective",models.TextField()),("status",models.CharField(default="draft",max_length=30)),
            ("owner",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="research_projects",to=settings.AUTH_USER_MODEL))]),
        migrations.AddField(model_name="researchsource",name="project",field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="sources",to="core.researchproject")),
    ]
