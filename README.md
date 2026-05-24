# Pip — AI Desktop Companion ![Static Badge](https://img.shields.io/badge/claude-code-orange)

[![Homepage](https://img.shields.io/badge/homepage-meet--pip.netlify.app-7860d4?style=flat-square)](https://meet-pip.netlify.app/)

A tiny pixel-art character who lives in the corner of your Linux desktop.
She chats, dances to your music, reminds you to drink water, and grows a real personality the longer you hang around.
Powered by Claude Code — **no API key needed**.

![Pip demo](marketing/assets/demo.gif)

---

## What she does

- **AI chat** — left-click to talk; uses your local `claude` CLI session
- **Voice input** — click the mic button and speak; Pip transcribes and replies
- **Google Calendar** — connect once and say *"add dentist Friday at 3pm"* or *"what's on my calendar today?"*
- **Relationship system** — grows from *New Friend* → *Best Friend* over 500+ interactions; her tone and humour actually change
- **Music awareness** — dances when a new track starts via `playerctl`; fetches artist facts
- **Games** — Trivia Quiz, 20 Questions, Rock-Paper-Scissors from the right-click menu
- **Wellness** — Pomodoro timer, hydration reminders, 4-7-8 breathing, screen-time nudges
- **Daily content** — word of the day, coding challenge, haiku, and time-aware greetings
- **Memory** — say `remember: X` to save a note; she brings it up later
- **Ambient awareness** — reacts to your clipboard, active window, CPU spikes, and weather

---

## Installation

```bash
# 0. Clone the repo
git clone https://github.com/gourab026/claude_companion.git
cd claude_companion

# 1. System dependencies
sudo apt install portaudio19-dev xdotool playerctl  # portaudio required for voice input

# 2. Python dependencies
pip install -r requirements.txt

# 3. Make sure Claude Code is installed and authenticated
claude -p "hi"   # should return a response

# 4. Run
python main.py
```

> A compositor (picom, KWin, etc.) must be running for transparency to work.

---

## Usage

| Action | Result |
|---|---|
| Left-click | Open chat |
| Double-click | Pet Pip |
| Triple-click | Minimize to a dot |
| Right-click | Context menu (games, Pomodoro, settings…) |
| Drag | Move anywhere on screen |
| `remember: X` in chat | Save a sticky note |
| `teach: word = meaning` | Teach Pip a new word |
| `play [song]` in chat | Open YouTube search |
| `remind me to X tomorrow at 3pm` | Add to Google Calendar |
| `what's on my calendar today?` | Read calendar events |

---

## Voice input

Click the 🎤 button in the chat window to speak instead of type.

```bash
# Required
pip install SpeechRecognition PyAudio

# Optional — offline transcription (no internet needed)
pip install openai-whisper
```

Switch between Google Speech (online) and Whisper (offline) in **Settings → Voice Input**.

---

## Google Calendar

1. Open the right-click menu → **Control Panel → Settings**
2. Scroll to **Google Calendar** → click **Connect**
3. Follow the one-time setup (Google Cloud credentials + browser login)

Once connected, natural language works:
- *"add team meeting Monday at 2pm"*
- *"remind me to call John tomorrow at 10am"*
- *"what do I have on Friday?"*

---

## Relationship levels

| Interactions | Level | What changes |
|---|---|---|
| 0–24 | New friend | Polite and curious |
| 25–99 | Acquaintance | Warmer, more casual |
| 100–499 | Friend | Playful and personal |
| 500+ | Best friend | Teases you, writes diary entries about your day |

---

## Control Panel

Right-click → **Control Panel** opens a 5-tab dashboard:

| Tab | Contents |
|---|---|
| 🏠 Home | Live stats, quick actions, mood chart, usage |
| 👤 Character | Personality traits, your profile, cosmetics |
| 📝 Memory | Notes, bookmarks, journal, mood history |
| ⚙️ Settings | AI model, voice, calendar, wellness, tools, MCP |
| 📋 Log | Live log viewer with level filtering |

---

## Stack

Python 3.9+ · PyQt6 · Claude Code CLI · `playerctl` · `xdotool` · `SpeechRecognition` · `PyAudio` · Google Calendar API

---

## License

[Polyform Noncommercial 1.0](LICENSE) — free for personal use, not for commercial products.
