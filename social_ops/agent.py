"""Bounded autonomous editorial agent: offline, auditable, no publishing or DMs."""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOPICS = {
 "personal": [
  ("Business", "One useful question before starting a new project", "A good project begins with a clear problem, a measurable goal and a realistic budget."),
  ("Research", "Why evidence matters", "Before sharing a strong claim, look for independent sources and distinguish facts from opinions."),
  ("Leadership", "A small habit that improves decisions", "Write down assumptions before committing resources, then revisit them after learning more.")
 ],
 "company": [
  ("Research", "مستندسازی پژوهش", "ثبت روش، منابع و محدودیت‌ها به ارزیابی دقیق‌تر نتایج پژوهش کمک می‌کند."),
  ("Education", "مدیریت منابع", "مدیریت منابع با سنجش هزینه، بازده و ریسک آغاز می‌شود."),
  ("Services", "تعریف مسئله", "پیش از سفارش خدمات تخصصی، هدف و معیار موفقیت را روشن کنید.")
 ],
 "vancouver_personal": [
  ("Food", "The little things that make a great dinner", "Good food, a warm atmosphere, and genuine conversation. What makes a memorable evening for you?"),
  ("Travel", "The beauty of discovering a new place", "Sometimes the best moments come from slowing down and noticing the details. Where would you go for a peaceful weekend?"),
  ("Lifestyle", "Style is in the details", "A simple outfit, good coffee and an interesting conversation can make an ordinary day special.")
 ]
}

def build(day=None):
 day = day or datetime.now(timezone.utc).date()
 results = {}
 for brand, items in TOPICS.items():
  index = day.toordinal() % len(items)
  category, title, caption = items[index]
  digest = hashlib.sha256(f"{brand}|{day}|{title}".encode()).hexdigest()[:12]
  results[brand] = {
   "id": digest, "brand": brand, "date_utc": day.isoformat(),
   "category": category, "title": title, "text": caption,
   "status": "draft_requires_review", "approved": False,
   "auto_publish": False, "media": [], "evidence_checked": False,
   "notes": "Editorial suggestion only. No real-world claims or media verified."
  }
 return results

def main():
 output = ROOT / "output"
 output.mkdir(exist_ok=True)
 for brand, item in build().items():
  (output / f"{brand}_agent_draft.json").write_text(
   json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
  print(f"{brand}: draft {item['id']} prepared, publication disabled")

if __name__ == "__main__":
 main()
