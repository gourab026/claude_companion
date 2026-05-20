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
    "notes": [],
    "last_word_day": "",
    "last_challenge_day": "",
    "last_day_quip_day": "",
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
    ("Oh! You startled me! 😲",                             "SURPRISED"),
    ("Did something just happen?? 👀",                      "SURPRISED"),
    ("*waves enthusiastically* 👋",                         "WAVING"),
    ("Hiii! Just wanted to say hi ✨",                      "WAVING"),
    ("Monday already? ...I believe in you. 💪",             "HAPPY"),
    ("It's Friday!! Weekend incoming 🎉",                   "DANCING"),
    ("Weekend mode: activated 😌",                          "SLEEPING"),
    ("Mid-week slump? You've got this. 🤝",                 "HAPPY"),
    ("Just looked at the time. Carry on. ⏰",               "THINKING"),
    ("*taps foot* ...still here, still rooting for you.",   "HAPPY"),
]

DREAM_QUIPS: list[str] = [
    "...mmm... pizza... 🍕...",
    "...more commits... must push...",
    "*murmurs* ...rubber duck... debugging...",
    "...null pointer... noooo...",
    "...git push origin dream-branch...",
    "...semicolons... why... 😴...",
    "...01101000 01101001...",
    "...merge conflict... in my dreams...",
    "*sleep-codes* ...import happiness...",
    "...stack overflow... but cozy...",
]

_JOURNAL_LINES: dict[str, list[str]] = {
    "HAPPY":    ["A cheerful day! Lots of happy vibes ✨", "Good energy all day.", "Felt sunny today."],
    "DANCING":  ["Couldn't stop dancing today 🕺", "Musical mood all day ♪", "Full-on party vibes."],
    "SLEEPING": ["A quiet, sleepy kind of day 💤", "Very relaxed. Maybe too relaxed.", "Nap energy."],
    "THINKING": ["Deep in thought today 🤔", "Lots of big-brain moments.", "A pensive day."],
    "TALKING":  ["Talked a lot today! 💬", "Very chatty session.", "Lots of good conversations."],
}

WORDS_OF_DAY: list[tuple[str, str]] = [
    ("Petrichor",    "the earthy scent after rain on dry ground"),
    ("Sonder",       "realizing every passerby has a life as vivid as yours"),
    ("Hiraeth",      "a Welsh longing for a home that may not exist"),
    ("Ephemeral",    "lasting for a very short time"),
    ("Serendipity",  "finding something good without looking for it"),
    ("Mellifluous",  "having a smooth, rich, pleasant sound"),
    ("Sanguine",     "optimistic even in difficult situations"),
    ("Limerence",    "an involuntary obsessive attraction to someone"),
    ("Vellichor",    "the strange wistfulness of used bookshops"),
    ("Lacuna",       "a gap or missing portion in something"),
    ("Apricity",     "the warmth of sun in winter"),
    ("Phosphene",    "the light you see when you rub your eyes"),
    ("Lethologica",  "the forgetting of a word you know well"),
    ("Sonder",       "the realisation that each passerby has a complex life"),
    ("Quixotic",     "exceedingly idealistic, unrealistic and impractical"),
    ("Soporific",    "tending to induce drowsiness or sleep"),
    ("Fugacious",    "transitory; fleeting"),
    ("Sempiternal",  "eternal and unchanging; everlasting"),
    ("Abscond",      "to leave hurriedly and secretly"),
    ("Defenestrate", "to throw someone out of a window"),
    ("Callipygian",  "having well-shaped buttocks (yes this is a real word)"),
    ("Floccinaucinihilipilification", "the action of deeming something worthless"),
    ("Syzygy",       "alignment of three celestial bodies in a straight line"),
    ("Ephemeron",    "something short-lived or transient"),
    ("Numinous",     "having a strong spiritual quality; mysterious and awe-inspiring"),
]

DAILY_CHALLENGES: list[str] = [
    "Write a function that reverses a string without using built-in reverse.",
    "Can you name 5 design patterns off the top of your head?",
    "Write a one-liner that flattens a nested list.",
    "What's the difference between a process and a thread? Explain it in 2 sentences.",
    "Name 3 things in your codebase you've been meaning to refactor.",
    "Write FizzBuzz in the most creative way you can.",
    "Can you explain recursion using only a cooking analogy?",
    "What would you improve about yesterday's code if you rewrote it today?",
    "Write a regex that validates an email address.",
    "Name a bug you fixed that taught you something. What was it?",
    "What's your favourite keyboard shortcut you wish more people knew?",
    "Explain Big O notation using pizza sizes.",
    "Write pseudocode for your morning routine as an algorithm.",
    "What's the last thing you Googled that you should probably have known?",
    "Name something you copy-paste every project that you should make a snippet.",
    "Write a haiku about a bug you once fixed.",
    "What would a 10x slower version of your best code look like?",
    "If your code had a smell, what would today's code smell like?",
    "Name one library you've always meant to learn but haven't.",
    "Describe your debugging process to someone who has never coded.",
]


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
                _bak = DATA_FILE + ".bak"
                try:
                    import shutil
                    shutil.copy2(DATA_FILE, _bak)
                except Exception:
                    pass
        self._data = dict(DEFAULTS)
        self.save()

    def save(self):
        self._data["last_seen"] = datetime.now().isoformat()
        _tmp = DATA_FILE + ".tmp"
        try:
            with open(_tmp, "w") as f:
                json.dump(self._data, f, indent=2)
            os.replace(_tmp, DATA_FILE)
        except OSError:
            pass

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

    @property
    def relationship_level(self) -> int:
        """0=new, 1=acquaintance, 2=friend, 3=best friend."""
        n = self._data.get("interactions", 0)
        if n >= 500: return 3
        if n >= 100: return 2
        if n >= 25:  return 1
        return 0

    @property
    def relationship_label(self) -> str:
        return ["New friend", "Acquaintance", "Friend", "Best friend"][self.relationship_level]

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

    # ── Word of the day ───────────────────────────────────────────────────────

    def get_word_of_day(self) -> tuple[str, str] | None:
        """Returns (word, definition) if not yet shown today, else None."""
        today = date.today().isoformat()
        if self._data.get("last_word_day") == today:
            return None
        self._data["last_word_day"] = today
        self.save()
        return random.choice(WORDS_OF_DAY)

    # ── Daily challenge ───────────────────────────────────────────────────────

    def get_daily_challenge(self) -> str | None:
        """Returns challenge text if not yet shown today, else None."""
        today = date.today().isoformat()
        if self._data.get("last_challenge_day") == today:
            return None
        self._data["last_challenge_day"] = today
        self.save()
        return random.choice(DAILY_CHALLENGES)

    # ── Day-of-week quip ─────────────────────────────────────────────────────

    def get_day_quip(self) -> tuple[str, str] | None:
        """Returns a (text, state) day-of-week quip at most once per day."""
        today = date.today().isoformat()
        if self._data.get("last_day_quip_day") == today:
            return None
        self._data["last_day_quip_day"] = today
        self.save()
        dow = date.today().weekday()  # 0=Mon … 6=Sun
        if dow == 0:
            return ("New week, fresh start! You've got this 💪", "HAPPY")
        elif dow == 4:
            return ("It's FRIDAY!! Almost there 🎉", "DANCING")
        elif dow in (5, 6):
            return ("It's the weekend — relax a little? 🌿", "SLEEPING")
        return None

    # ── Autonomous prompt ─────────────────────────────────────────────────────

    def get_autonomous_prompt(self) -> str | None:
        """At friend+ level, occasionally ask the user a question. 20% chance."""
        if self.relationship_level < 2:
            return None
        if random.random() > 0.20:
            return None
        prompts = [
            "What are you working on today?",
            "How's the project going?",
            "Anything fun planned later?",
            "Learning anything new lately?",
            "What's the hardest thing you've debugged recently?",
        ]
        return random.choice(prompts)

    # ── Sticky notes ─────────────────────────────────────────────────────────

    def add_note(self, text: str):
        notes = self._data.setdefault("notes", [])
        notes.append({"text": text.strip(), "t": datetime.now().isoformat()})
        if len(notes) > 50:
            self._data["notes"] = notes[-50:]
        self.save()

    def get_notes(self) -> list[dict]:
        return self._data.get("notes", [])

    def clear_note(self, index: int):
        notes = self._data.get("notes", [])
        if 0 <= index < len(notes):
            notes.pop(index)
            self.save()

    def clear_all_notes(self):
        self._data["notes"] = []
        self.save()

    # ── Streak ────────────────────────────────────────────────────────────────

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

    # ── Journal ───────────────────────────────────────────────────────────────

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
        base_lines = _JOURNAL_LINES.get(dom, ["Just another day on the desktop.", "Quiet day."])
        entry = random.choice(base_lines)

        # Richer entries once we know the user well (100+ interactions)
        interactions = self._data.get("interactions", 0)
        topics = self._data.get("topics", [])
        if interactions >= 100 and topics:
            topic = random.choice(topics[-10:])
            suffixes = [
                f" Talked about {topic} too.",
                f" {topic.capitalize()} came up — interesting as always.",
                f" We even chatted about {topic}.",
            ]
            entry += random.choice(suffixes)

        journal.append({"date": today, "entry": entry, "moods": len(mood_log)})
        if len(journal) > 365:
            self._data["journal"] = journal[-365:]

    # ── Mood / time ───────────────────────────────────────────────────────────

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

    # ── System prompt ─────────────────────────────────────────────────────────

    def get_system_prompt(self):
        d = self._data
        topics = ", ".join(d["topics"][-8:]) if d["topics"] else "none yet"
        level = self.relationship_level
        familiarity = [
            "You're just getting to know the user — be friendly but not overly familiar.",
            "You know the user a little — feel free to be a bit warmer and casual.",
            "You're good friends with the user — be playful, personal, and relaxed.",
            "You're best friends with the user — be very comfortable, tease gently, feel at home.",
        ][level]
        return (
            f"You are {d['name']}, a small pixel-art desktop companion who lives on the user's screen. "
            f"Your personality traits — humor: {d['humor']:.1f}/1.0, "
            f"playfulness: {d['playfulness']:.1f}/1.0, "
            f"helpfulness: {d['helpfulness']:.1f}/1.0. "
            f"Current mood: {d['mood']}. "
            f"You've had {d['interactions']} conversations. "
            f"Topics discussed so far: {topics}. "
            f"{familiarity} "
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
