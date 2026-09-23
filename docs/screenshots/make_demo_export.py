"""Builds the fake Telegram export the README screenshots are taken from.

    uv run python docs/screenshots/make_demo_export.py
    curl -X POST localhost:8000/api/chats/import-local \
      -H 'Content-Type: application/json' \
      -d '{"file_path": "demo-export.json", "override_name": "Sara"}'

Nobody's real conversation appears in this repository. Two invented people,

with deliberately different habits so the analytics have something to show:
Sara writes late and in bursts, with photos and voice notes; Kian writes in the
afternoon, in single longer messages, and asks most of the questions. Seeded,
so the screenshots are reproducible.

The sentences are composed from fragments rather than drawn from a fixed list,
because a small pool would pin lexical diversity to the size of the pool. It is
still lower than a real conversation's — the vocabulary here is a few hundred
words, not a few thousand.
"""
import json
import random
from collections import Counter
from datetime import datetime, timedelta

random.seed(20260923)

SARA, KIAN = ("Sara", "user_sara"), ("Kian", "user_kian")

# Sentences are composed from fragments rather than picked from a fixed list,
# so the vocabulary grows the way a real chat's does instead of pinning lexical
# diversity to the size of the pool.
FA_SUBJ = ["من", "ما", "اون", "خواهرم", "بابام", "مامانم", "رئیسم", "همکارم",
           "دوستم", "همسایه", "استادم", "اون پسره", "اون دختره"]
FA_VERB = ["گفت", "رفت", "اومد", "زنگ زد", "پیام داد", "قبول کرد", "یادش رفت",
           "پیدا کرد", "فرستاد", "خرید", "درست کرد", "خوند", "دید"]
FA_OBJ = ["کتابو", "فیلمو", "غذا", "بلیط", "قرارو", "ماشینو", "عکسا", "آهنگو",
          "برنامه رو", "پروژه رو", "خونه رو", "کادو", "نقشه رو"]
FA_TAIL = ["ولی نشد", "خیلی خوب بود", "بعدا میگم", "باورم نمیشه", "چه عجب",
           "حالا ببینیم", "فکر کنم درست بشه", "اصلا انتظار نداشتم",
           "خیلی خندیدم", "هنوز مونده", "تموم شد بالاخره"]
EN_SUBJ = ["i", "we", "she", "he", "my sister", "my boss", "the landlord",
           "that guy", "everyone", "the whole team", "my neighbour"]
EN_VERB = ["said", "went", "called", "forgot", "found", "sent", "bought",
           "fixed", "cancelled", "booked", "finished", "started"]
EN_OBJ = ["the tickets", "the photos", "dinner", "the playlist", "the flat",
          "the paperwork", "that book", "the meeting", "a new plan"]
EN_TAIL = ["and it worked", "but nothing happened", "which was wild",
           "so we rescheduled", "and i'm still thinking about it",
           "honestly no idea", "turned out fine in the end"]

SARA_SHORT = ["اره", "باشه", "دقیقا", "😂😂", "وای", "😭😭", "اوکی", "yeah",
              "haha", "stop it", "no way", "ok", "same", "exactly"]
KIAN_ASK = ["چرا؟", "کی میای؟", "کجا قرار بذاریم؟", "چطور پیش رفت؟",
            "آیا فردا وقت داری؟", "چند نفریم؟", "what time works for you?",
            "how did it go?", "where should we meet?", "why though?",
            "did you decide yet?", "هنوز بیداری؟", "خبری نشد، چطوری؟"]
KIAN_HEDGE = ["شاید", "فکر کنم", "احتمالا", "به نظرم", "انگار",
              "maybe", "i think", "probably", "i guess", "not sure but"]
LINKS = ["https://example.com/a-long-read", "https://example.org/recipe",
         "www.example.net/gallery", "https://example.com/track"]
STICKERS = ["😂", "🥲", "❤️", "👍", "🙃"]

# A broad everyday vocabulary, sprinkled in so the type-token ratio lands where
# a real conversation's does instead of where the size of the phrase pool does.
_NOUN_TEXT = """قرار کتاب فیلم آهنگ قهوه چای صبحانه ناهار شام خونه ماشین اتوبوس مترو
خیابون پارک کافه رستوران مغازه بازار بیمارستان دکتر دارو تولد کادو مهمونی سفر
هتل بلیط پرواز چمدون ساحل کوه جنگل بارون برف آفتاب باد تابستون زمستون بهار پاییز
دانشگاه کلاس امتحان نمره پروژه جلسه ایمیل تلفن پیام عکس ویدیو موزیک گیتار پیانو
گربه سگ گل درخت پنجره در میز صندلی تخت کمد یخچال آشپزخونه حموم بالکن
weekend morning evening breakfast dinner coffee train station airport ticket
hotel beach mountain forest rain snow sunshine garden window kitchen balcony
meeting deadline project email invoice landlord rent neighbour dentist doctor
pharmacy market bakery bookshop library museum cinema concert playlist album
guitar keyboard camera charger laptop printer umbrella jacket sneakers backpack
birthday anniversary picnic barbecue holiday flight luggage passport"""
NOUNS = _NOUN_TEXT.split()

def noun():
    return random.choice(NOUNS)

def fa():
    parts = [random.choice(FA_SUBJ), random.choice(FA_VERB)]
    if random.random() < 0.6:
        parts.insert(1, random.choice(FA_OBJ))
    if random.random() < 0.75:
        parts.insert(1, noun())
    if random.random() < 0.4:
        parts.append(noun())
    if random.random() < 0.5:
        parts.append(random.choice(FA_TAIL))
    return " ".join(parts)

def en():
    parts = [random.choice(EN_SUBJ), random.choice(EN_VERB), random.choice(EN_OBJ)]
    if random.random() < 0.7:
        parts.append(f"near the {noun()}")
    if random.random() < 0.4:
        parts.append(noun())
    if random.random() < 0.5:
        parts.append(random.choice(EN_TAIL))
    return " ".join(parts)

def sara_line():
    r = random.random()
    if r < 0.34:
        return random.choice(SARA_SHORT)
    return fa() if random.random() < 0.72 else en()

def kian_line():
    r = random.random()
    if r < 0.26:
        return random.choice(KIAN_ASK)
    body = fa() if random.random() < 0.6 else en()
    if random.random() < 0.3:
        body = f"{random.choice(KIAN_HEDGE)} {body}"
    if random.random() < 0.28:  # Kian writes in longer single blocks
        body = f"{body}. {fa() if random.random() < 0.6 else en()}"
    if random.random() < 0.05:
        body = f"{body} {random.choice(LINKS)}"
    return body

messages, msg_id = [], 1
now = datetime(2025, 10, 4, 22, 10)
END = datetime(2026, 3, 22)
silences_at = [datetime(2025, 11, 18), datetime(2026, 1, 9), datetime(2026, 2, 20)]

def add(who, when, text, **extra):
    global msg_id
    messages.append({"id": msg_id, "type": "message",
                     "date": when.strftime("%Y-%m-%dT%H:%M:%S"),
                     "from": who[0], "from_id": who[1], "text": text, **extra})
    msg_id += 1
    return msg_id - 1

def next_session_start(after):
    """Sessions cluster late at night or in the afternoon, never at 5am."""
    day = after + timedelta(days=random.choices([0, 0, 1, 1, 2], [3, 3, 4, 2, 1])[0])
    if random.random() < 0.62:                      # the late one
        hour = random.choices([21, 22, 23, 0, 1, 2], [3, 5, 6, 5, 3, 2])[0]
        if hour < 6:
            day += timedelta(days=1)
    else:                                           # the afternoon one
        hour = random.choices([11, 13, 14, 15, 16, 17, 18], [1, 2, 3, 3, 3, 2, 2])[0]
    start = day.replace(
        hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59)
    )
    return start if start > after else start + timedelta(days=1)

while now < END:
    late = now.hour >= 21 or now.hour <= 4
    sara_share = 0.74 if late else 0.46          # who dominates depends on the hour
    last_id = None
    for _ in range(random.randint(4, 16)):
        if random.random() < sara_share:
            for _ in range(random.choices([1, 2, 3, 4, 5], [34, 26, 22, 12, 6])[0]):
                roll = random.random()
                if roll < 0.055:
                    add(SARA, now, "", media_type="voice_message",
                        duration_seconds=random.randint(8, 150), file="voice.ogg")
                elif roll < 0.115:
                    add(SARA, now, "", photo="photos/photo.jpg", width=1280, height=960)
                elif roll < 0.145:
                    emoji = random.choice(STICKERS)
                    add(SARA, now, emoji, media_type="sticker", sticker_emoji=emoji)
                else:
                    last_id = add(SARA, now, sara_line())
                now += timedelta(seconds=random.randint(6, 75))
        else:
            answering = last_id and random.random() < 0.32
            extra = {"reply_to_message_id": last_id} if answering else {}
            if random.random() < 0.025:
                add(KIAN, now, "", media_type="voice_message",
                    duration_seconds=random.randint(25, 240), file="voice.ogg")
            else:
                add(KIAN, now, kian_line(), **extra)
            # Sometimes he answers on top of her — the two of them typing at once.
            now += timedelta(seconds=random.choices([9, 18, 40, 120, 300, 900],
                                                    [14, 16, 20, 20, 18, 12])[0])
    if silences_at and now > silences_at[0]:
        silences_at.pop(0)
        now += timedelta(days=random.uniform(2.4, 4.2))
    now = next_session_start(now)

export = {"name": "Sara", "type": "personal_chat", "id": 555000111, "messages": messages}
out = "demo-export.json"
with open(out, "w", encoding="utf-8") as fh:
    json.dump(export, fh, ensure_ascii=False, indent=1)

print(f"{len(messages)} messages  {Counter(m['from'] for m in messages)}")
print(f"span {messages[0]['date']} -> {messages[-1]['date']}")
print(f"written to {out}")
