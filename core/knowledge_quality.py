"""Scientific/editorial quality gates for the public Knowledge platform."""

QUALITY_GATES = (
    "problem_definition", "scope_and_taxonomy", "source_provenance",
    "evidence_quality", "methodology", "fact_check", "uncertainty",
    "peer_review", "seo_structure", "internal_linking", "publication_control",
)

CONTENT_LAYERS = {
    "reference": "دانش مرجع و تعریف‌های مستند",
    "research": "یافته و تحلیل پژوهشی با منشأ روشن",
    "technical": "روش‌ها، استانداردها و چارچوب‌های مهندسی",
    "historical": "اطلاعات تاریخی با تفکیک منبع و روایت",
    "practical": "راهنمای کاربردی با مرزبندی علمی و ایمنی",
    "glossary": "تعریف اصطلاحات و روابط مفهومی",
}

SEO_REQUIREMENTS = (
    "search_intent", "canonical_topic", "pillar_cluster_relation",
    "semantic_entities", "faq_candidates", "title_meta", "structured_headings",
    "internal_links", "related_topics", "freshness_signal",
)

def quality_contract():
    return {
        "free_public_access": True,
        "scientific_first": True,
        "source_required_for_claims": True,
        "uncertainty_must_be_explicit": True,
        "fabricated_sources_forbidden": True,
        "publication_requires_review": True,
        "quality_gates": list(QUALITY_GATES),
        "content_layers": CONTENT_LAYERS,
        "seo_requirements": list(SEO_REQUIREMENTS),
    }
