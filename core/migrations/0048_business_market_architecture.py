from django.db import migrations, models
import django.db.models.deletion

def seed_units(apps, schema_editor):
    Unit=apps.get_model("core","BusinessUnit"); Policy=apps.get_model("core","MarketPolicy")
    units=[
      ("games","Games & Interactive","digital","active","US",False),
      ("digital-products","Digital Products","digital","active","GLOBAL",True),
      ("services","Global Services","services","active","GLOBAL",True),
      ("ai-software","AI & Software","technology","active","GLOBAL",True),
      ("research-media","Research & Media","knowledge","active","GLOBAL",True),
      ("web3","Blockchain & Web3","technology","planned","GLOBAL",True),
      ("agro-industry","Agro-Industry","production","future","CA",True),
    ]
    for code,name,category,status,market,glob in units:
        u=Unit.objects.create(code=code,name=name,category=category,status=status,primary_market=market,global_scope=glob)
        if code=="games": Policy.objects.create(business_unit=u,market_code="US",role="primary",status="target")
        elif glob: Policy.objects.create(business_unit=u,market_code="GLOBAL",role="primary",status="target")

class Migration(migrations.Migration):
    dependencies=[("core","0047_crypto_payments")]
    operations=[
      migrations.CreateModel(name="BusinessUnit",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),("code",models.SlugField(unique=True)),("name",models.CharField(max_length=160)),("category",models.CharField(max_length=80)),("status",models.CharField(default="future",max_length=24)),("description",models.TextField(blank=True)),("primary_market",models.CharField(blank=True,max_length=80)),("global_scope",models.BooleanField(default=False)),("metadata",models.JSONField(blank=True,default=dict))]),
      migrations.CreateModel(name="LegalEntity",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),("code",models.SlugField(unique=True)),("name",models.CharField(max_length=200)),("jurisdiction",models.CharField(max_length=80)),("status",models.CharField(default="future",max_length=24)),("registration_reference",models.CharField(blank=True,max_length=160)),("verified_at",models.DateTimeField(blank=True,null=True)),("metadata",models.JSONField(blank=True,default=dict))]),
      migrations.CreateModel(name="MarketPolicy",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),("market_code",models.CharField(max_length=16)),("role",models.CharField(default="eligible",max_length=24)),("status",models.CharField(default="planned",max_length=24)),("notes",models.TextField(blank=True)),("business_unit",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="market_policies",to="core.businessunit"))],options={"constraints":[models.UniqueConstraint(fields=("business_unit","market_code"),name="unique_business_unit_market")]}),
      migrations.RunPython(seed_units,migrations.RunPython.noop),
    ]
