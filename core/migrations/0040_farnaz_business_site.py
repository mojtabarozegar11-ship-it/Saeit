from django.db import migrations, models


SERVICES = [
    ("architectural-drafting", "Architectural drafting", "Draft and organize architectural plans, elevations, sections and presentation sheets from an agreed brief.", 10),
    ("cad-review", "CAD review and cleanup", "Improve layers, dimensions and drawing clarity; prepare organized editable CAD files.", 20),
    ("bim-visualization", "3D modelling and visualization", "Translate approved drawings into spatial models and visual references for review and presentation.", 30),
    ("project-consultation", "Project consultation and estimate", "Review the brief, available files and scope, then propose a timeline and estimate before work begins.", 40),
]
OFFERS = [
    ("project-drawing", "service", "Project service", "Agree scope, provide milestone files and coordinate review before final delivery.", 10),
    ("cad-starter-kit", "digital", "CAD template pack", "Downloadable drawing sheets and templates; details and pricing can be set in the admin.", 20),
    ("drafting-workshop", "training", "Drafting workshop", "Practical learning sessions covering drafting, layer organization and file preparation.", 30),
    ("design-consultation", "consultation", "Project consultation", "A scheduled conversation to clarify a project question and the right next step.", 40),
]
PROJECTS = [
    ("Concept sample — residential plan set", "Architectural drafting", "Concept sample showing a presentation sheet layout. This is not a completed or approved client project.", 10),
    ("Concept sample — workplace", "Spatial presentation", "Concept study showing one way to connect a plan and 3D presentation.", 20),
    ("Concept sample — drawing details", "CAD documentation", "Concept sample of layer organization, dimensions and a review-ready file.", 30),
]


def seed_farnaz_content(apps, schema_editor):
    Service = apps.get_model("core", "FarnazService")
    Offer = apps.get_model("core", "FarnazOffer")
    Project = apps.get_model("core", "FarnazProject")
    for slug, title, summary, order in SERVICES:
        Service.objects.get_or_create(slug=slug, defaults={
            "title": title, "summary": summary, "active": True, "sort_order": order,
        })
    for title, kind, description, order in OFFERS:
        Offer.objects.get_or_create(title=title, defaults={
            "kind": kind, "description": description, "active": True,
            "checkout_enabled": False, "sort_order": order,
        })
    for title, discipline, summary, order in PROJECTS:
        Project.objects.get_or_create(title=title, defaults={
            "discipline": discipline, "summary": summary, "is_concept": True,
            "active": True, "sort_order": order,
        })


class Migration(migrations.Migration):
    dependencies = [("core", "0039_educationassessment_educationattempt_and_more")]
    operations = [
        migrations.CreateModel(
            name="FarnazService",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180)),
                ("slug", models.SlugField(unique=True)),
                ("summary", models.CharField(max_length=360)),
                ("details", models.TextField(blank=True)),
                ("image_url", models.URLField(blank=True)),
                ("starting_price", models.DecimalField(blank=True, decimal_places=0, max_digits=14, null=True)),
                ("price_currency", models.CharField(default="USD", max_length=12)),
                ("active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ("sort_order", "id"), "verbose_name": "Farnaz service", "verbose_name_plural": "Farnaz services"},
        ),
        migrations.CreateModel(
            name="FarnazProject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180)),
                ("discipline", models.CharField(max_length=100)),
                ("summary", models.TextField()),
                ("image_url", models.URLField(blank=True)),
                ("is_concept", models.BooleanField(default=True)),
                ("active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ("sort_order", "id"), "verbose_name": "Farnaz portfolio item", "verbose_name_plural": "Farnaz portfolio"},
        ),
        migrations.CreateModel(
            name="FarnazOffer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180)),
                ("kind", models.CharField(choices=[("consultation", "Consultation"), ("digital", "Digital product"), ("training", "Training"), ("service", "Project service")], max_length=24)),
                ("description", models.TextField()),
                ("cover_url", models.URLField(blank=True)),
                ("price", models.DecimalField(blank=True, decimal_places=0, max_digits=14, null=True)),
                ("currency", models.CharField(default="USD", max_length=12)),
                ("checkout_enabled", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ("sort_order", "id"), "verbose_name": "Farnaz offer", "verbose_name_plural": "Farnaz offers"},
        ),
        migrations.CreateModel(
            name="FarnazInquiry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("phone", models.CharField(max_length=40)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("category", models.CharField(choices=[("drawing", "Drafting and documentation"), ("cad", "CAD review and cleanup"), ("bim", "3D modelling and visualization"), ("digital", "Digital files or products"), ("training", "Training"), ("consulting", "Consultation and estimate")], max_length=24)),
                ("message", models.TextField(max_length=3000)),
                ("consent", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("new", "New"), ("contacted", "Contacted"), ("quoted", "Estimate sent"), ("closed", "Closed")], default="new", max_length=16)),
            ],
            options={"ordering": ("-created_at",), "verbose_name": "Farnaz enquiry", "verbose_name_plural": "Farnaz enquiries"},
        ),
        migrations.RunPython(seed_farnaz_content, migrations.RunPython.noop),
    ]
