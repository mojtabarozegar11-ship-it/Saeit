"""Produce two separate, offline, non-publishing editorial draft queues."""
import json
from datetime import datetime, timezone
from pathlib import Path

TOPICS = {
    "personal": [
        ("اقتصاد تولید", "سه پرسش کلیدی پیش از سرمایه‌گذاری در یک کسب‌وکار تولیدی"),
        ("مدیریت", "چگونه هزینه‌های ثابت و متغیر را در تصمیم‌گیری جدا کنیم؟"),
        ("آموزش", "تفاوت درآمد، سود و جریان نقدی در مدیریت کسب‌وکار"),
    ],
    "company": [
        ("پژوهش", "چرا مستندسازی شواهد برای توسعه محصول اهمیت دارد؟"),
        ("کشاورزی", "نقش مدیریت منابع در پایداری تولید کشاورزی"),
        ("خدمات", "چگونه یک درخواست خدمات پژوهشی را دقیق تعریف کنیم؟"),
    ],
}

def main():
    output = Path("social_ops/output")
    output.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    for brand, topics in TOPICS.items():
        drafts = [
            {"id": f"{brand}-{index:03}", "brand": brand, "category": category,
             "title": title, "status": "draft_requires_review",
             "text": f"{title}\n\nبرای انتشار، متن مستند و مثال‌های معتبر باید تکمیل و بررسی شوند.",
             "created_at": timestamp}
            for index, (category, title) in enumerate(topics, 1)
        ]
        (output / f"{brand}_drafts.json").write_text(
            json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{brand}: {len(drafts)} offline drafts generated; none published")

if __name__ == "__main__":
    main()
