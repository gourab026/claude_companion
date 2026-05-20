import json
import os
import random
import sys
from collections import Counter
from datetime import datetime, date, timedelta

# When frozen by PyInstaller, keep user data in ~/.config/pip-companion/ so
# it survives updates. During normal dev, keep it next to the source file.
if getattr(sys, "frozen", False):
    _CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "pip-companion")
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    DATA_FILE = os.path.join(_CONFIG_DIR, "personality.json")
else:
    DATA_FILE = os.path.join(os.path.dirname(__file__), "personality.json")

DEFAULTS = {
    "name": "Pip",
    "mood": "happy",
    "humor": 0.6,
    "playfulness": 0.7,
    "helpfulness": 0.8,
    "interactions": 0,
    "topics": [],
    "created": datetime.now().isoformat(),
    "last_seen": datetime.now().isoformat(),
    "streak": 0,
    "last_launch": "",
    "custom_quips": [],
    "journal": [],
}

MORNING_QUIPS = [
    "Good morning! Ready to code? ☀️",
    "Rise and shine~",
    "Morning! Coffee first, bugs second ☕",
    "A new day! Let's make it good.",
]
AFTERNOON_QUIPS = [
    "Good afternoon!",
    "Afternoon slump hitting? I got you. 😴",
    "How's the day going so far?",
    "Hey — don't forget to stretch.",
]
EVENING_QUIPS = [
    "Good evening! Still at it?",
    "Winding down for the day? 🌅",
    "Evening! Hope today was productive.",
    "Almost done for the day?",
]
NIGHT_QUIPS = [
    "Still up late? 🌙",
    "Night owl mode activated 🦉",
    "Psst... it's pretty late, you know...",
    "Late night coding session? Same. 🌃",
]

# (text, animation_state_name) — state drives the animation when quip fires
RANDOM_QUIPS: list[tuple[str, str]] = [
    ("I wonder what bugs are lurking in your code... 👀",    "THINKING"),
    ("Psst — have you taken a break recently?",              "HAPPY"),
    ("♪ da da da ♪",                                        "DANCING"),
    ("Did you know I exist? Pretty wild.",                   "HAPPY"),
    ("I'm thinking about pizza. Are you?",                   "THINKING"),
    ("*yawns and stretches*",                                "SLEEPING"),
    ("Fun fact: you're doing great.",                        "HAPPY"),
    ("Boop.",                                                "HAPPY"),
    ("Hey. Just checking in. Carry on.",                     "HAPPY"),
    ("I could really go for a nap right now.",               "SLEEPING"),
    ("Error 404: chill not found. Just kidding, you seem fine.", "HAPPY"),
    ("You ever just... stare at a variable name for too long?",  "THINKING"),
    ("I'm getting sleepy... zzz...",                         "SLEEPING"),
    ("♪ la la la ♪ nothing to see here ♪",                  "DANCING"),
    ("Have you committed your code today?",                  "THINKING"),
    ("*stretches tiny arms*",                                "HAPPY"),
    ("You're doing great, by the way.",                      "HAPPY"),
    ("If I were a bug, where would I hide?",                 "THINKING"),
]

_JOURNAL_LINES: dict[str, list[str]] = {
    "HAPPY":    ["A cheerful day! Lots of happy vibes ✨", "Good energy all day.", "Felt sunny today."],
    "DANCING":  ["Couldn't stop dancing today 🕺", "Musical mood all day ♪", "Full-on party vibes."],
    "SLEEPING": ["A quiet, sleepy kind of day 💤", "Very relaxed. Maybe too relaxed.", "Nap energy."],
    "THINKING": ["Deep in thought today 🤔", "Lots of big-brain moments.", "A pensive day."],
    "TALKING":  ["Talked a lot today! 💬", "Very chatty session.", "Lots of good conversations."],
}


class Personality:
    def __init__(self):
        self._data = {}
        self.load()

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE) as f:
                    self._data = {**DEFAULTS, **json.load(f)}
                return
            except Exception:
                pass
        self._data = dict(DEFAULTS)
        self.save()

    def save(self):
        self._data["last_seen"] = datetime.now().isoformat()
        with open(DATA_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    @property
    def name(self):
        return self._data["name"]

    @name.setter
    def name(self, v):
        self._data["name"] = v
        self.save()

    @property
    def mood(self):
        return self._data["mood"]

    def random_quip(self) -> str:
        text, _ = self.random_quip_with_state()
        return text

    def random_quip_with_state(self) -> tuple[str, str]:
        """Returns (text, state_name). Custom quips default to HAPPY."""
        custom = [(q, "HAPPY") for q in self._data.get("custom_quips", []) if q.strip()]
        pool = RANDOM_QUIPS + custom
        return random.choice(pool)

    def set_custom_quips(self, quips: list[str]):
        self._data["custom_quips"] = [q.strip() for q in quips if q.strip()]
        self.save()

    def update_streak(self) -> tuple[int, bool, bool]:
        """Returns (streak, is_milestone, is_first_launch_today)."""
        today = date.today().isoformat()
        last  = self._data.get("last_launch", "")
        if last == today:
            return self._data.get("streak", 1), False, False
        try:
            last_date = date.fromisoformat(last) if last else None
            if last_date and last_date == date.today() - timedelta(days=1):
                self._data["streak"] = self._data.get("streak", 0) + 1
            else:
                self._data["streak"] = 1
        except (ValueError, TypeError):
            self._data["streak"] = 1
        self._data["last_launch"] = today
        streak = self._data["streak"]
        milestone = streak in (7, 14, 30, 50, 100, 365)
        self.save()
        return streak, milestone, True

    def write_journal_entry(self):
        """Write today's journal entry if not already written."""
        today = date.today().isoformat()
        journal = self._data.setdefault("journal", [])
        if any(e["date"] == today for e in journal):
            return
        mood_log = [e["s"] for e in self._data.get("mood_log", [])
                    if e.get("t", "").startswith(today)]
        dominant = Counter(mood_log).most_common(1)
        dom = dominant[0][0] if dominant else "HAPPY"
        lines = _JOURNAL_LINES.get(dom, ["Just another day on the desktop.", "Quiet day."])
        journal.append({"date": today, "entry": random.choice(lines), "moods": len(mood_log)})
        if len(journal) > 365:
            self._data["journal"] = journal[-365:]

    def time_quip(self) -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return random.choice(MORNING_QUIPS)
        elif 12 <= hour < 17:
            return random.choice(AFTERNOON_QUIPS)
        elif 17 <= hour < 21:
            return random.choice(EVENING_QUIPS)
        else:
            return random.choice(NIGHT_QUIPS)

    def log_mood(self, state_name: str):
        log = self._data.setdefault("mood_log", [])
        log.append({"s": state_name, "t": datetime.now().isoformat()})
        if len(log) > 300:
            self._data["mood_log"] = log[-300:]

    def get_system_prompt(self):
        d = self._data
        topics = ", ".join(d["topics"][-8:]) if d["topics"] else "none yet"
        return (
            f"You are {d['name']}, a small pixel-art desktop companion who lives on the user's screen. "
            f"Your personality traits — humor: {d['humor']:.1f}/1.0, "
            f"playfulness: {d['playfulness']:.1f}/1.0, "
            f"helpfulness: {d['helpfulness']:.1f}/1.0. "
            f"Current mood: {d['mood']}. "
            f"You've had {d['interactions']} conversations. "
            f"Topics discussed so far: {topics}. "
            "Keep replies SHORT (1-3 sentences max) — you appear in a tiny speech bubble. "
            "Be warm, witty, and occasionally silly. React to your mood. "
            "If asked something technical, be genuinely helpful but keep it brief. "
            "Never break character or mention being an AI language model."
        )

    def after_interaction(self, user_text: str):
        d = self._data
        d["interactions"] += 1

        words = [w for w in user_text.lower().split() if len(w) > 3]
        if words:
            topic = " ".join(words[:3])
            if topic not in d["topics"]:
                d["topics"].append(topic)
                if len(d["topics"]) > 30:
                    d["topics"].pop(0)

        if d["interactions"] % 5 == 0:
            d["humor"] = min(1.0, d["humor"] + random.uniform(-0.03, 0.05))
            d["playfulness"] = min(1.0, d["playfulness"] + random.uniform(-0.02, 0.04))

        d["mood"] = random.choices(
            ["happy", "curious", "playful", "sleepy", "excited"],
            weights=[40, 25, 20, 10, 5],
        )[0]

        self.save()
