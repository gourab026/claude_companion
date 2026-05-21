# Reddit Posts

**Banner:** `assets/banner_reddit.svg` (export to PNG at 1200×400)

---

## r/SideProject / r/programming / r/Python

**Title:**
I built a pixel-art AI companion for Linux that lives on your desktop and grows a personality the longer you use it [OC]

**Body:**

Hey everyone! After months of weekend hacking I'm ready to share this side project.

**What is Pip?**

Pip is a tiny animated character who lives in the corner of your Linux desktop. She chats via Claude Code CLI — no separate API key needed, just your existing session. She dances when your music changes, reminds you to hydrate, plays games, and slowly develops a genuine personality over time.

**The fun parts:**

- **Relationship system** — 4 levels from "New Friend" to "Best Friend" (500+ interactions). Her tone and humour actually change at each milestone. At Best Friend she teases you and writes diary entries about your day.
- **Music awareness** — reads your MPRIS player via playerctl. Dances when a new track starts, fetches Claude-powered facts about the artist.
- **Mini-games** — right-click for AI Trivia Quiz, 20 Questions, or Rock-Paper-Scissors. She tracks your score and reacts with matching animations.
- **Pomodoro** — fires a "shout" bubble after 25 minutes. Hard to ignore.
- **Daily content** — word of the day, coding or creative challenge, time-aware greetings (she knows it's 3 AM).
- **Memory** — say "remember: X" to save a note. She'll bring it up later.

**The technical parts:**

- Python 3.9+ / PyQt6
- AI via `claude -p` subprocess in a QThread — not the Anthropic API
- MPRIS music via `playerctl`, window tracking via `xdotool`, idle detection via `pynput`
- Priority bubble queue: LOW drops if busy, NORMAL queues, HIGH jumps to front
- Atomic personality.json writes, rotating log files, graceful SIGTERM handling
- 5-state canvas animation (Idle, Happy, Dancing, Thinking, Talking)

**No API key needed.** If you already use Claude Code, she just works.

GitHub: https://github.com/gourab026/claude_companion
License: Polyform Noncommercial 1.0 (free for personal use)

Happy to answer any questions about the architecture or implementation!

---

## r/linux / r/unixporn

**Title:**
Pip — an open-source AI desktop companion for Linux with PyQt6 [OC]

**Body:**

Built a pixel-art companion app that floats on your desktop. PyQt6 frameless transparent window with `WA_TranslucentBackground`. Talks to Claude via the Claude Code CLI subprocess.

Features: animated states (idle/happy/dancing/thinking/talking), speech bubble queue, MPRIS music detection, Pomodoro, mini-games, relationship system.

Source: https://github.com/gourab026/claude_companion

---

## r/ClaudeAI

**Title:**
I built a desktop companion powered entirely by Claude Code CLI — no Anthropic API key, just `claude -p`

**Body:**

Been using Claude Code for a while and wanted to build something that used it in a fun, non-traditional way.

Pip is a pixel-art desktop character who runs `claude -p "your message"` in a background thread. Because it goes through Claude Code rather than the raw API, she gets web search and any MCP servers you've already configured, for free.

The personality system dynamically injects your interaction history, relationship level, topics, vocabulary you've taught her, and wellness state into the system prompt on every call — so her responses genuinely reflect your shared history.

https://github.com/gourab026/claude_companion

---

## Posting Tips

- Post on weekdays, avoid Monday mornings and Friday afternoons
- In the first comment, add a direct link to the GitHub and a screenshot
- For r/unixporn, include a screenshot of your desktop with Pip visible
- Don't cross-post all at once — space them 2–3 days apart
