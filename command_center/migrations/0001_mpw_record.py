from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="MpwRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tenant", models.CharField(db_index=True, default="mojplaywin-main", editable=False, max_length=40)),
                ("kind", models.CharField(choices=[("content", "Page row/card"), ("offer", "Store offer"), ("job", "Production/editorial job"), ("agent_outcome", "Evidence-backed agent outcome")], db_index=True, max_length=20)),
                ("key", models.SlugField(max_length=100, unique=True)),
                ("page_path", models.CharField(db_index=True, default="/", max_length=200)),
                ("title", models.CharField(max_length=200)),
                ("draft", models.JSONField(default=dict)),
                ("published_snapshot", models.JSONField(blank=True, default=dict)),
                ("state", models.CharField(choices=[("draft", "Draft"), ("review", "Quality review"), ("needs_revision", "Needs revision"), ("awaiting_approval", "Awaiting approval"), ("approved", "Approved"), ("published", "Published")], default="draft", max_length=24)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("quality_note", models.TextField(blank=True)),
                ("quality_evidence", models.CharField(blank=True, max_length=240)),
                ("approval_evidence", models.CharField(blank=True, max_length=240)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ("kind", "key")},
        ),
        migrations.AddIndex(model_name="mpwrecord", index=models.Index(fields=["tenant", "kind", "page_path"], name="mpw_tenant_kind_page")),
    ]
