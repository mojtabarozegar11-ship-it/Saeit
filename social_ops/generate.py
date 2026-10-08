"""Offline editorial drafts for the initial three-brand pilot. Never publishes."""
import json
from datetime import datetime, timezone
from pathlib import Path

TOPICS = {
    "personal": [
        ("Production economics", "Three questions to ask before investing in a production business"),
        ("Management", "How to distinguish fixed and variable costs in business decisions"),
        ("Business education", "Revenue, profit and cash flow: why the difference matters"),
    ],
    "company": [
        ("پژوهش", "چرا مستندسازی شواهد برای توسعه محصول اهمیت دارد؟"),
        ("کشاورزی", "نقش مدیریت منابع در پایداری تولید کشاورزی"),
        ("خدمات", "چگونه یک درخواست خدمات پژوهشی را دقیق تعریف کنیم؟"),
    ],
    "mojplaywin": [
        ("Game design", "Three principles of fair and engaging game design"),
        ("Digital products", "How to evaluate a digital product before launch"),
        ("Community", "Why player feedback matters for a game roadmap"),
    ],
}

def main():
    config = json.loads(Path("social_ops/brands.json").read_text(encoding="utf-8"))
    active = {brand["id"] for brand in config["brands"]}
    if active != set(TOPICS):
        raise ValueError("Brand registry and draft topics differ")
    output = Path("social_ops/output")
    output.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    for brand, topics in TOPICS.items():
        drafts = [
            {"id": f"{brand}-{index:03}", "brand": brand, "category": category,
             "title": title, "status": "draft_requires_review",
             "text": title, "created_at": timestamp}
            for index, (category, title) in enumerate(topics, 1)
        ]
        (output / f"{brand}_drafts.json").write_text(
            json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{brand}: {len(drafts)} drafts generated; none published")

if __name__ == "__main__":
    main()
