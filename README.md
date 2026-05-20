# Pip — Pixel-Art Desktop Companion [![Claude Code](https://shields.io)](https://code.claude.com)

A transparent, always-on-top desktop companion for Linux that lives on your screen,
talks to you through the Claude Code CLI, and develops a personality over time.
**No Anthropic API key required** — Pip uses your existing Claude Code session.

---

## Features

### Core
- Pixel-art animated character with 7 states: idle bob, talking, happy, thinking, sleeping, dancing, dragging
- AI-powered conversation via local `claude` CLI
- Persistent speech bubbles (3 styles: speech, thought, shout) — click to dismiss early, duration scales with word count
- Draggable and always-on-top via `WindowStaysOnTopHint`; never steals focus from the user's active window
- **Triple-click to minimize** — triple-click Pip to shrink her to a tiny purple dot; triple-click the dot to restore
- **Mood color tinting** — Pip's body color slowly lerps to match the current mood state

### Personality & Mood
- **Mood reactions** — animation reacts to keywords in your message and Pip's own reply
- **Personality drift** — humor and playfulness shift slightly with every 5 interactions
- **Relationship levels** — Pip grows from *New friend* → *Acquaintance* → *Friend* → *Best friend* as interactions accumulate; her conversational tone adapts accordingly
- **Conversation history** — Pip remembers the last 3 exchanges per session
- **Mood history chart** — Control Panel shows today's mood breakdown as a bar chart
- **Daily journal** — a one-line diary entry written at shutdown; references recent topics after 100+ interactions; readable in the Journal tab

### Fun Interactions
- **Time-aware greetings** — good morning / afternoon / evening / night on first launch; "welcome back" on subsequent launches
- **Streak tracking** — milestone messages at 7, 14, 30, 50, 100, and 365 consecutive days
- **Birthday celebration** — on the anniversary of Pip's creation day, she dances and counts the days together
- **Dream muttering** — Pip mutters surreal dream thoughts in a thought bubble during sleep animations
- **Word of the day** — one obscure word + definition shown once per calendar day (thought bubble)
- **Daily challenge** — one coding or creative prompt shown once per calendar day (thought bubble)
- **Double-click to pet Pip** — happy reaction and a "hehe~ ♡" bubble, no AI call
- **Drag reaction** — surprised DRAGGING face with speed lines; "wheee! ✨" on drop
- **Clipboard watcher** — copies 30+ chars → Pip offers to explain; git commit SHAs → Pip dances and cheers
- **Typing-aware idle** — 20 min without typing → Pip checks in with a break reminder
- **Screen-time nudge** — 2 continuous hours at the desk → Pip tells you to take a real break (re-arms after 90 min)
- **Random idle events** — dance, sleep, quips, haiku, time-aware greetings fire on a configurable timer; each quip drives its matching animation
- **Pip's haiku** — random idle event: Pip generates a fresh 5-7-5 haiku via Claude in a thought bubble
- **Active window watcher** — every 30 s Pip peeks at the active window title and comments (browser, coding, terminal, YouTube, Discord, Spotify…)
- **Music detector** — reads the active MPRIS player via `playerctl` every 45 s; Pip dances and names the track when a new song starts; with 30 % chance (and a 10-min minimum gap) Pip fetches an interesting fact about the song or artist via Claude and shows it in a thought bubble
- **System stats commentator** — checks CPU/RAM via `psutil` every 5 min; reacts with concern when usage spikes above 85 %
- **Weather reactions** — fetches local weather from `wttr.in` once per session; Pip's mood and bubble match the conditions
- **Pomodoro timer** — 25-min focus session from the right-click menu; SHOUT bubble when done
- **Rock-Paper-Scissors** — quick game from the right-click menu with matching animations
- **Trivia quiz** — right-click → Pip asks a Claude-generated question, judges your answer, keeps score
- **20 Questions** — right-click → Claude picks a secret, you ask up to 20 yes/no questions
- **Sticky notes** — say "remember: X" in chat to save a note; view and delete notes in Control Panel
- **Twin Pip** — summon a second companion from the menu; they wave, react, and play together
- **Custom quips** — add your own idle phrases in the Control Panel

### Bubble Styles
| Style | Appearance | Used for |
|-------|-----------|---------|
| `speech` | Rounded rect, triangle tail | Chat replies, quips, greetings |
| `thought` | More rounded, dot-chain tail, blue tint | Haiku, word of day, challenge, dream, notes confirm |
| `shout` | Spiky star-burst border, warm tint | Git commits, RPS result, pomodoro done, screen-time |

### Tools & Integration
- Web search support via `--allowedTools WebSearch,WebFetch`
- Custom MCP server connections (stdio and HTTP/SSE) managed via the Control Panel
- Fun MCP presets in `mcp_config.example.json` (time, fetch, filesystem, sequential-thinking)

### Distribution
- **AppImage packaging** — single portable `Pip-Companion-x86_64.AppImage` runs on any x86_64 Linux distro with no Python install needed; rebuilt with `bash build_appimage.sh`

---

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                     User Desktop                        │
│                                                         │
│   ┌──────────────┐  left-click / double-click / drag    │
│   │  Pip Window  │ ◄────────────────────────────────    │
│   │ (transparent │                                       │
│   │  QWidget)    │  paintEvent clears to transparent,   │
│   │              │  then CharacterRenderer draws        │
│   │    [Pip]     │  directly into the window painter.   │
│   └──────┬───────┘                                       │
│          │ left-click (single)                          │
│          ▼                                               │
│   ┌──────────────┐    ┌────────────────────────────┐    │
│   │  Chat input  │───►│      ClaudeWorker           │    │
│   │  (QDialog)   │    │  (QThread)                  │    │
│   └──────────────┘    │  subprocess.run(            │    │
│                       │    "claude -p" ...)          │    │
│   ┌──────────────┐    └────────────────────────────┘    │
│   │ Speech Bubble│◄── response_ready signal             │
│   │ (3 styles,   │                                       │
│   │  click=hide) │                                       │
│   └──────────────┘                                       │
│                                                         │
│   pynput listener  ──►  _last_keypress (typing idle)    │
│   QClipboard signal ─►  git SHA / clipboard watcher     │
│   xdotool thread   ──►  _react_to_window (win watcher)  │
│   playerctl thread ──►  _react_to_music (MPRIS)         │
│   psutil thread    ──►  _react_to_stats (CPU/RAM)       │
│   urllib thread    ──►  _react_to_weather (wttr.in)     │
│   personality.json ──►  mood_log, traits, notes, topics │
│   QSettings        ──►  model, idle interval, position  │
└─────────────────────────────────────────────────────────┘
```

### Why no child widgets?

On Linux/X11 the parent window's ARGB visual (which enables transparency) does **not**
propagate to child QWidgets. Child widgets get their own X11 window with a default
opaque background, which appears as a black box. The fix: draw everything directly
in the top-level window's `paintEvent`, with `CompositionMode_Clear` first to erase
to transparent, then `CompositionMode_SourceOver` to paint the character on top.

---

## Architecture

```
companion/
├── main.py            Entry point. CompanionWindow owns all timers and state.
│                      Draws character directly in its paintEvent.
│                      Handles: clipboard watcher (+ git SHA detection), pynput
│                      keyboard listener, window watcher (xdotool thread), music
│                      detector (playerctl thread), system stats (psutil thread),
│                      weather fetch (urllib thread), dream muttering, haiku,
│                      word of day, daily challenge, screen-time nudge, sticky notes,
│                      trivia quiz, 20 questions, twin Pip, pomodoro, RPS.
│
├── character.py       CharacterRenderer — pure drawing class (not a QWidget).
│                      7-state animation machine: IDLE, TALKING, HAPPY, THINKING,
│                      SLEEPING, DANCING, DRAGGING.
│                      tick_color() lerps body colour toward per-state tint target.
│                      IDLE frame advances only every 4th tick (~2 fps).
│
├── personality.py     Personality — loads/saves personality.json.
│                      Tracks mood, traits, interaction count, topics, mood_log,
│                      streak, journal, custom_quips, notes, last_word_day,
│                      last_challenge_day. Provides: time_quip(), log_mood(),
│                      update_streak(), write_journal_entry(), get_word_of_day(),
│                      get_daily_challenge(), add_note(), get_notes(), clear_note().
│                      relationship_level / relationship_label properties.
│                      get_system_prompt() includes familiarity tone per level.
│
├── claude_client.py   ClaudeWorker (QThread) — runs `claude -p` in background.
│                      Supports --allowedTools and --mcp-config flags.
│                      Emits response_ready or error_occurred signals.
│
├── bubble.py          BubbleWindow — separate top-level transparent QWidget.
│                      Three styles: speech (default rounded + triangle tail),
│                      thought (rounded + dot-chain tail, blue tint),
│                      shout (spiky star-burst border, warm tint).
│                      Click to dismiss. Duration scales with word count.
│                      Text rendered via QRect + AlignVCenter for consistent margins
│                      (PADDING_H=14 left/right, PADDING_V=12 top/bottom, MAX_WIDTH=300).
│
├── control_panel.py   ControlPanel QWidget with 7 tabs:
│                        Personality    — name, traits, mood, topics, custom quips,
│                                         relationship level, reset
│                        Mood History   — bar chart of today's mood events
│                        Journal        — last 30 diary entries, newest first
│                        Notes 📌       — view, delete, clear sticky notes
│                        Tools & MCP    — web search toggle, MCP server manager
│                        Settings       — model, idle interval, position reset
│                        About          — help text
│                      McpServerDialog — add/edit stdio or HTTP MCP servers.
│
├── pip_companion.spec PyInstaller spec — builds the onedir bundle used in the AppImage.
│
├── build_appimage.sh  One-command rebuild: PyInstaller → AppDir → AppImage.
│
├── mcp_config.example.json  Example MCP server configs (time, fetch, filesystem,
│                            sequential-thinking). Copy to mcp_config.json to use.
│
├── personality.json   Auto-created on first run. (gitignored)
│                      When running from AppImage: ~/.config/pip-companion/personality.json
│
├── mcp_config.json    Auto-created via Control Panel. (gitignored)
│                      When running from AppImage: ~/.config/pip-companion/mcp_config.json
│
└── requirements.txt   PyQt6>=6.4.0, pynput>=1.7.0, psutil>=5.9 (optional)
```

---

## Installation

```bash
# 1. Install Python dependencies
pip install PyQt6 pynput
pip install psutil   # optional — needed for system stats commentator

# 2. Make sure Claude Code CLI is installed and authenticated
claude --version     # should print a version number
claude -p "hi"       # should return a response

# 3. Run
cd /path/to/companion
python main.py
```

> A compositor (picom, KWin, Mutter, etc.) must be running for transparency to work.
> On bare X11 without a compositor, the window background will appear black.
>
> pynput requires `/dev/input` or X11 event hooks. If typing-idle doesn't work:
> `sudo usermod -aG input $USER` (logout/login required).
>
> `xdotool` is needed for the window-watcher: `sudo apt install xdotool`
>
> `playerctl` is needed for music detection: `sudo apt install playerctl`

---

## AppImage (portable, no Python needed)

Download the pre-built `Pip-Companion-x86_64.AppImage` from the repo, then:

```bash
chmod +x Pip-Companion-x86_64.AppImage
./Pip-Companion-x86_64.AppImage
```

User data is stored in `~/.config/pip-companion/` so it persists across updates.

**Still required on the target machine:**
- `claude` CLI (authenticated)
- `xdotool` — `sudo apt install xdotool`
- `playerctl` — `sudo apt install playerctl` (for music detection)
- A compositor for transparency

**Rebuild the AppImage after code changes:**
```bash
pip install pyinstaller --break-system-packages
cd companion/
bash build_appimage.sh   # outputs ../Pip-Companion-x86_64.AppImage
```

---

## Usage

| Action | Result |
|--------|--------|
| Left-click Pip | Open chat input |
| Double-click Pip | Pet Pip — happy reaction, no AI call |
| Triple-click Pip | Minimize to tiny purple dot (triple-click dot to restore) |
| Right-click Pip | Context menu |
| Drag Pip | Move to any screen position; "wheee!" on drop |
| Click speech bubble | Dismiss it early |
| Right-click → Chat | Open chat input |
| Right-click → Control Panel | Open settings, personality editor, notes, MCP config |
| Right-click → Start Pomodoro 🍅 | Start/stop 25-minute focus timer |
| Right-click → Rock Paper Scissors 🪨 | Quick game against Pip |
| Right-click → Trivia Quiz 🎯 | Claude asks a trivia question; Pip keeps score |
| Right-click → 20 Questions 🔍 | Pip thinks of something; ask up to 20 yes/no questions |
| Right-click → My Notes 📌 | Show saved sticky notes |
| Right-click → Summon Twin 👯 | Spawn a second Pip; they interact with each other |
| Right-click → Clear History | Wipe this session's conversation memory |
| Right-click → Rename | Rename Pip |
| Chat: "remember: X" | Save X as a sticky note without an AI call |

---

## Feature Details

### Clipboard Watcher

When you copy text longer than 30 characters, Pip offers to explain it — left-click Pip
to open the chat with it pre-filled. If the clipboard looks like a **git commit output**
(contains a commit SHA), Pip dances and cheers instead.

### Typing-Aware Idle & Screen-Time Nudge

- **20 min no typing** → break reminder (resets after each)
- **2 continuous hours active** → more urgent "take a real break" nudge in a shout bubble;
  re-arms automatically after 90 minutes

### Relationship Levels

| Interactions | Level | Pip's tone |
|---|---|---|
| 0–24 | New friend | Friendly but polite |
| 25–99 | Acquaintance | Warmer and casual |
| 100–499 | Friend | Playful, personal |
| 500+ | Best friend | Very comfortable, teases gently |

Shown in **Control Panel → Personality → Relationship**.

### Word of the Day & Daily Challenge

Both fire once per calendar day on startup (with a short delay so they don't overlap
the greeting). Word of the day uses a thought bubble to show an obscure word and its
definition. Daily challenge shows a coding or creative prompt.

### Dream Muttering

When a random sleep event fires, Pip enters SLEEPING state for ~12 seconds. After
4–8 seconds she mutters a surreal dream thought in a thought bubble before waking up.

### Pip's Haiku

A random idle event (10% weight) triggers Pip to ask Claude for a coding-themed haiku.
While Claude is thinking, Pip shows THINKING state. The haiku appears in a thought bubble.

### Music Detector & Song Facts

Every 45 seconds Pip runs `playerctl metadata` in a background thread. When a new track
starts playing she switches to DANCING and names the song.

With a **30 % chance** (and a minimum 10-minute gap between facts) Pip fires a background
Claude call asking for one surprising fact about that song or artist. The fact appears
8 seconds later in a **thought bubble** — after the dance reaction has faded — so it
never collides with the initial greeting. If Pip doesn't recognise the song she falls
back to a fact about the artist.

Silently skips if `playerctl` is not installed (`sudo apt install playerctl`).

### System Stats Commentator

Every 5 minutes Pip runs `psutil.cpu_percent()` and `psutil.virtual_memory()` in a
background thread. Reacts if CPU > 85 % or RAM > 88 %. Silently skips if `psutil`
is not installed (`pip install psutil`).

### Weather Reactions

Once per session, ~8 seconds after launch, Pip fetches `wttr.in/?format=%C+%t` in a
background thread. The condition string (sunny/rain/storm/snow/cloud…) determines
Pip's state and bubble text. Silently skips if the network is unavailable.

### Trivia Quiz

Right-click → **Trivia Quiz**. Pip uses two Claude calls: one to generate a
`QUESTION: / ANSWER:` formatted question, and one to judge your free-text answer.
Wins and losses are tracked in memory for the session and shown in the result bubble.

### 20 Questions

Right-click → **20 Questions**. Claude picks a concrete secret (animal, object, or
person). You ask yes/no questions via dialog boxes; Claude answers each one. The game
ends when you guess correctly or exhaust all 20 questions.

### Sticky Notes

Type `remember: your note` (or `note: your note`) in the chat input — Pip stores the
note locally without making an AI call and confirms with a thought bubble. View, select,
and delete notes in **Control Panel → Notes 📌**.

### Twin Pip

Right-click → **Summon Twin**. A second identical Pip window appears next to the
original. Every 20–40 seconds they exchange waves, music notes, or greetings. Right-click
→ **Dismiss Twin** to close the second window.

### Triple-Click to Minimize

Triple-clicking Pip within 600 ms shrinks her window to a **20×20 purple dot** — useful
when she's in the way but you don't want to quit. The animation and idle timers pause,
and the bubble hides. Triple-clicking the dot restores full size and resumes all timers.

Qt generates `mousePressEvent → mouseDoubleClickEvent → mousePressEvent` for a triple
click, so click timestamps are tracked in both handlers.

### Mood Color Tinting

Pip's body color lerps (3 % per animation tick) toward a per-state target:

| State | Colour |
|---|---|
| IDLE | Neutral purple |
| HAPPY | Warm yellow-purple |
| DANCING | Pink-purple |
| SLEEPING | Cool blue |
| THINKING | Deep blue-purple |
| TALKING | Slight teal-purple |
| DRAGGING | Vivid violet |

### Mood History Chart & Daily Journal

- **Mood History** — colour-coded bar chart of today's mood events in the Control Panel
- **Journal** — one-line diary entry written at shutdown; references recent conversation
  topics once 100+ interactions have accumulated; capped at 365 entries

### Active Window Watcher

Every 30 s Pip checks the active window title (via `xdotool`) and with 35 % chance
comments on what you're doing. Only fires when Pip is IDLE.

### Time-Aware Greetings & Streak

On the **first launch of each day**:
- 5 am – 12 pm → morning quip
- 12 pm – 5 pm → afternoon quip
- 5 pm – 9 pm → evening quip
- 9 pm – 5 am → night quip

Streak milestones fire at **7, 14, 30, 50, 100, 365** days.

### Enabling Web Search

Open **Control Panel → Tools & MCP**, check **Enable Web Search**, save.
This passes `--allowedTools WebSearch,WebFetch` to the Claude CLI.

### Fun MCP Servers

Copy `mcp_config.example.json` to `mcp_config.json` and enable MCP in
**Control Panel → Tools & MCP**:

| Server | What it does | Requires |
|--------|-------------|---------|
| `time` | Pip knows the current time in any timezone | `pip install uvx` |
| `fetch` | Pip can read any URL/webpage | Node.js |
| `filesystem` | Pip can read files in a directory you specify | Node.js |
| `sequential-thinking` | Step-by-step reasoning for complex problems | Node.js |

---

## Configuration Reference

### personality.json

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Pip's name |
| `mood` | string | Current mood (happy / curious / playful / sleepy / excited) |
| `humor` | float 0–1 | How funny Pip tries to be |
| `playfulness` | float 0–1 | How often Pip jokes vs. stays on topic |
| `helpfulness` | float 0–1 | How much detail Pip gives on technical questions |
| `interactions` | int | Total conversation count (drives relationship level) |
| `topics` | list[str] | Up to 30 recent topics discussed |
| `mood_log` | list[obj] | Up to 300 recent mood events `{s, t}` |
| `streak` | int | Consecutive daily launch count |
| `last_launch` | ISO date | Date of last launch |
| `custom_quips` | list[str] | User-defined random idle phrases |
| `journal` | list[obj] | Up to 365 daily diary entries `{date, entry, moods}` |
| `notes` | list[obj] | Sticky notes `{text, t}`, capped at 50 |
| `last_word_day` | ISO date | Date word-of-the-day was last shown |
| `last_challenge_day` | ISO date | Date daily challenge was last shown |
| `created` | ISO datetime | When Pip was first run |
| `last_seen` | ISO datetime | Last save timestamp |

### QSettings keys (`companion/pip`)

| Key | Default | Description |
|-----|---------|-------------|
| `model` | `claude-sonnet-4-6` | Claude model used |
| `idle_min` | `30` | Min seconds between random idle events |
| `idle_max` | `90` | Max seconds between random idle events |
| `allowed_tools` | `""` | Comma-separated tool names (e.g. `WebSearch,WebFetch`) |
| `use_mcp` | `false` | Whether to pass `--mcp-config` to Claude |
| `x` / `y` | bottom-right | Saved window position |

---

## TODO — Features to Add

### Cross-platform

- [ ] **Windows support** — replace `xdotool` with `pywin32` (`win32gui`) for window watcher; replace `playerctl` with Windows Media Control API (`winsdk`); PyInstaller → `.exe`; ship as a zip or NSIS installer
- [ ] **macOS support** — replace `xdotool` with `pyobjc` / AppleScript for window watcher; replace `playerctl` with AppleScript (`osascript`) or `pyobjc-framework-MediaPlayer` for Spotify/Music; PyInstaller → `.app` bundle → `hdiutil` → `.dmg`
- [ ] **CI build matrix** — GitHub Actions workflow that builds AppImage (Linux), `.exe` (Windows), `.dmg` (macOS) on every tag

### Features
- [x] **Music detector + song facts** — playerctl/MPRIS track detection; random Claude fact about the song/artist in a thought bubble (30 % chance, 10-min gap)
- [ ] **Voice output** — TTS via `espeak` / `pyttsx3` / `festival` for spoken responses
- [ ] **Voice input** — microphone button using `SpeechRecognition` or `whisper`
- [x] **Triple-click to minimize** — shrinks to a 20×20 dot; triple-click to restore
- [ ] **Multiple characters** — switch between different pixel-art skins
- [ ] **Notification hooks** — Pip comments on desktop notifications (calendar events, mail, etc.)
- [ ] **Screen-aware Pip** — Pip moves out of the way of full-screen windows
- [x] **Mini-games** — Rock-Paper-Scissors, Trivia Quiz, 20 Questions
- [x] **Custom quips** — user-editable list of random idle phrases in the Control Panel
- [ ] **Theme editor** — change Pip's color palette in the control panel
- [ ] **Startup on login** — add a `.desktop` autostart entry
- [x] **Multiple bubble styles** — speech, thought (dot-chain tail), shout (spiky border)
- [ ] **Wayland support** — test and fix `wl_surface` layering for Wayland compositors
- [ ] **Export / import personality** — share `personality.json` between machines
- [ ] **Streaming responses** — show Claude's reply word-by-word as it arrives
- [x] **Trivia / 20 Questions** — Claude-powered games from the right-click menu
- [x] **Word of the day** — obscure word + definition once per day
- [x] **Daily challenge** — coding/creative prompt once per day
- [x] **Dream muttering** — surreal sleep-state thought bubbles
- [x] **Haiku** — Claude-generated 5-7-5 haiku as a random idle event
- [x] **Screen-time nudge** — 2-hour reminder with re-arm
- [x] **Relationship levels** — tone adapts as interaction count grows
- [x] **Sticky notes** — "remember: X" shortcut + Notes tab in Control Panel
- [x] **Music detector** — playerctl/MPRIS reactions
- [x] **Weather reactions** — wttr.in once per session
- [x] **Git commit detector** — clipboard SHA → celebratory reaction
- [x] **System stats** — CPU/RAM commentary via psutil
- [x] **Twin Pip** — summon a second companion that interacts with the first

---

## TODO — Optimizations

- [ ] **Dirty-rect repaints** — only repaint the region that actually changed
- [ ] **Pre-rasterize frames** — cache each animation frame to a `QPixmap` at startup
- [x] **Adaptive frame rate** — IDLE advances only every 4th tick (~2 fps); active states at full 8 fps
- [ ] **Background worker pool** — reuse a single `QThread` instead of a new one per request
- [ ] **Subprocess warm-up** — keep Claude process warm to avoid cold-start latency
- [ ] **Debounce idle reschedule** — avoid restarting `_idle_timer` on rapid settings changes
- [x] **Bubble text margins** — QRect-based drawText with AlignVCenter; consistent PADDING_H/V; MAX_WIDTH 300
- [ ] **Bubble text caching** — cache laid-out lines so `_update_geometry` only re-runs on text change
- [ ] **Reduce QSettings writes** — batch position saves; currently writes on every mouseRelease
- [ ] **Lazy-import control panel** — import `control_panel.py` only when first opened
