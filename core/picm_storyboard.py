"""PICM owner-only shot planner. A plan is NOT generated video.

Produces bounded deterministic clip specs for a private GPU worker to consume
once a real compatible image-to-video GPU is configured. No provider calls.
"""
import re

DURATIONS = {5: (5,), 10: (5, 5), 30: (6, 6, 6, 6, 6),
             60: (6, 6, 6, 6, 6, 6, 6, 6, 6, 6)}
RATIOS = {"wide": "16:9", "vertical": "9:16"}
MORNING = (
    "همان فرد در اتاق‌خواب به‌آرامی چشم‌هایش را باز می‌کند",
    "همان فرد روی تخت می‌نشیند، کش‌وقوس می‌آید و از تخت بلند می‌شود",
    "همان فرد به آشپزخانه می‌رود و صبحانه را آماده می‌کند",
    "همان فرد پشت میز می‌نشیند و صبحانه می‌خورد",
    "همان فرد لباس مناسب محل کار را از کمد انتخاب می‌کند",
    "همان فرد لباس می‌پوشد و برای خروج آماده می‌شود",
    "همان فرد از خانه خارج می‌شود و در را پشت سرش می‌بندد",
    "همان فرد در مسیر محل کار حرکت می‌کند",
    "همان فرد وارد محل کار می‌شود و به همکاران سلام می‌کند",
    "همان فرد پشت میز یا محل فعالیت خود شروع به کار می‌کند",
)
DEFAULT = (
    "معرفی شخصیت اصلی با حفظ دقیق ویژگی‌های عکس مرجع",
    "شخصیت اصلی اولین اقدام داستان را در محیط مرتبط انجام می‌دهد",
    "ادامهٔ طبیعی اتفاقات و حرکت بدن در همان روایت",
    "تغییر نمای دوربین در خدمت روایت بدون تغییر هویت شخصیت",
    "شخصیت اصلی داستان را با یک کنش مشخص به پایان می‌رساند",
)


def _story_actions(text):
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) < 4 or len(clean) > 1500:
        raise ValueError("invalid_story_length")
    if any(term in clean.casefold() for term in ("خواب", "صبحانه", "لباس", "سر کار", "محل کار")):
        return MORNING
    parts = [a.strip(" .،؛:!") for a in re.split(r"[\n.!؟؛]+|،\s*بعد\s*|\s+سپس\s+|\s+بعد\s+", clean)
             if len(a.strip()) >= 4]
    if len(parts) >= 2:
        return tuple("همان شخصیت: " + a for a in parts[:12])
    return ("همان شخصیت: " + clean,) + DEFAULT


def plan_story(prompt, duration, ratio):
    if type(prompt) is not str or type(duration) is not int or duration not in DURATIONS:
        raise ValueError("unsupported_story")
    if ratio not in RATIOS:
        raise ValueError("invalid_ratio")
    actions = _story_actions(prompt)
    sizes = DURATIONS[duration]
    scenes = []
    time_at = 0
    for i, seconds in enumerate(sizes):
        # Cover the whole narrative, with the first and final beats always included.
        j = round(i * (len(actions) - 1) / max(len(sizes) - 1, 1))
        action = actions[j]
        scenes.append({
            "shot": i + 1,
            "start": time_at,
            "end": time_at + seconds,
            "duration": seconds,
            "action": action,
            "identity": "same_reference_person",
            "source": "private_reference_image",
            "camera": "natural cinematic motion with action-driven cuts",
            "conditioning": "reference image and previous clip final frame if supported",
            "status": "waiting_for_real_gpu_renderer",
        })
        time_at += seconds
    assert time_at == duration
    return {
        "duration": duration,
        "ratio": RATIOS[ratio],
        "format": "mp4_when_rendered",
        "actual_video_ready": False,
        "render_state": "awaiting_gpu",
        "requires": ["real_image_to_video_model", "gpu_compute", "clip_stitcher"],
        "scenes": scenes,
    }
