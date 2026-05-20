import json
import os
import random
from datetime import datetime

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

RANDOM_QUIPS = [
    "I wonder what bugs are lurking in your code... 👀",
    "Psst — have you taken a break recently?",
    "♪ da da da ♪",
    "Did you know I exist? Pretty wild.",
    "I'm thinking about pizza. Are you?",
    "*yawns and stretches*",
    "Fun fact: you're doing great.",
    "Boop.",
    "Hey. Just checking in. Carry on.",
    "I could really go for a nap right now.",
    "Error 404: chill not found. Just kidding, you seem fine.",
    "You ever just... stare at a variable name for too long?",
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

    def random_quip(self):
        return random.choice(RANDOM_QUIPS)

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
