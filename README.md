# Pip — Pixel-Art Desktop Companion

A transparent, always-on-top desktop companion for Linux that lives on your screen,
talks to you through the Claude Code CLI, and develops a personality over time.
**No Anthropic API key required** — Pip uses your existing Claude Code session.

---

## Features

### Core
- Pixel-art animated character with 7 states: idle bob, talking, happy, thinking, sleeping, dancing, dragging
- AI-powered conversation via local `claude` CLI
- Persistent speech bubbles that scale duration to text length — click a bubble to dismiss it early
- Draggable and always-on-top; position saved on release
- **Mood color tinting** — Pip's body color slowly shifts to match the current mood state (lerp at 3%/tick)

### Personality & Mood
- **Mood reactions** — animation reacts to keywords in your message and Pip's own reply
- **Personality drift** — humor and playfulness shift slightly with every 5 interactions
- **Conversation history** — Pip remembers the last 3 exchanges per session
- **Mood history chart** — Control Panel shows today's mood breakdown as a bar chart
- **Daily journal** — a one-line diary entry is written at shutdown based on the day's dominant mood; readable in the Journal tab

### Fun Interactions
- **Time-aware greetings** — Pip says good morning / afternoon / evening / night on first launch of the day; "welcome back" on subsequent launches
- **Streak tracking** — counts consecutive daily launch days; special milestone messages at 7, 14, 30, 50, 100, and 365 days
- **Birthday celebration** — on the anniversary of Pip's creation day, Pip dances and tells you how many days you've been together
- **Double-click to pet Pip** — triggers a happy reaction and a "hehe~ ♡" bubble, no AI call needed
- **Drag reaction** — Pip shows a surprised DRAGGING face with speed lines; says "wheee! ✨" on drop
- **Clipboard watcher** — when you copy something substantial (30+ chars), Pip offers to explain it; click Pip to accept with the text pre-filled in the chat
- **Typing-aware idle** — if you stop typing for 20+ minutes, Pip checks in with a break reminder
- **Random idle events** — dance, sleep, quips, time-aware check-ins, and random thoughts fire on a configurable timer; each quip drives its matching animation
- **Active window watcher** — every 30s Pip sneaks a peek at the active window title and comments (browser, terminal, editor, YouTube, Discord, Spotify…)
- **Pomodoro timer** — 25-minute focus session from the right-click menu; Pip dances when time's up
- **Rock-Paper-Scissors** — quick game from the right-click menu; Pip wins, loses, or ties with matching animations
- **Custom quips** — add your own random idle phrases in the Control Panel; they fire alongside built-in ones

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
│   └──────────────┘    │                             │    │
│                       │  subprocess.run(            │    │
│   ┌──────────────┐    │    "claude -p"              │    │
│   │ Speech Bubble│◄───│    --model ...              │    │
│   │ (top-level   │    │    --system-prompt ...      │    │
│   │  QWidget,    │    │    --allowedTools ...       │    │
│   │  click=hide) │    │    --mcp-config ...         │    │
│   └──────────────┘    │  )                          │    │
│                       └────────────────────────────┘    │
│                                                         │
│   pynput listener  ──►  _last_keypress (typing idle)    │
│   QClipboard signal ─►  _clipboard_pending (watcher)    │
│   xdotool thread   ──►  _react_to_window (win watcher)  │
│   personality.json  ──►  mood_log, traits, topics        │
│   QSettings         ──►  model, idle interval, position │
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
│                      Handles clipboard watcher, pynput keyboard listener,
│                      window watcher (xdotool in daemon thread), pomodoro,
│                      and Rock-Paper-Scissors.
│
├── character.py       CharacterRenderer — pure drawing class (not a QWidget).
│                      7-state animation machine: IDLE, TALKING, HAPPY, THINKING,
│                      SLEEPING, DANCING, DRAGGING.
│                      tick_color() lerps body colour toward per-state tint target.
│
├── personality.py     Personality — loads/saves personality.json.
│                      Tracks mood, traits, interaction count, topics, mood_log,
│                      streak, journal, custom_quips.
│                      Generates system prompt. Provides time_quip(), log_mood(),
│                      update_streak(), write_journal_entry().
│
├── claude_client.py   ClaudeWorker (QThread) — runs `claude -p` in background.
│                      Supports --allowedTools and --mcp-config flags.
│                      Emits response_ready or error_occurred signals.
│
├── bubble.py          BubbleWindow — separate top-level transparent QWidget.
│                      Draws a rounded-rect speech bubble with a tail.
│                      Click to dismiss. Duration scales with word count.
│
├── control_panel.py   ControlPanel QWidget with 6 tabs:
│                        Personality    — name, traits, mood, topics, custom quips, reset
│                        Mood History   — bar chart of today's mood events
│                        Journal        — last 30 diary entries, newest first
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
├── personality.json   Auto-created on first run. Stores name, mood,
│                      humor/playfulness/helpfulness, interaction count,
│                      topics list, mood_log, streak, journal, custom_quips,
│                      and timestamps. (gitignored)
│                      When running from AppImage: ~/.config/pip-companion/personality.json
│
├── mcp_config.json    Auto-created when you add an MCP server via the
│                      Control Panel. Passed to `claude --mcp-config`. (gitignored)
│                      When running from AppImage: ~/.config/pip-companion/mcp_config.json
│
└── requirements.txt   PyQt6>=6.4.0, pynput>=1.7.0
```

---

## Installation

```bash
# 1. Install Python dependencies
pip install PyQt6 pynput

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
> pynput requires access to `/dev/input` or X11 event hooks. If the typing-idle feature
> doesn't work, try running with `sudo` or add your user to the `input` group:
> `sudo usermod -aG input $USER` (logout/login required).
>
> xdotool is needed for the window-watcher feature: `sudo apt install xdotool`

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
- `xdotool` — `sudo apt install xdotool` (for window-watcher)
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
| Right-click Pip | Context menu |
| Drag Pip | Move to any screen position; "wheee!" on drop |
| Click speech bubble | Dismiss it early |
| Right-click → Chat | Open chat input |
| Right-click → Control Panel | Open settings, personality editor, MCP config |
| Right-click → Start Pomodoro 🍅 | Start/stop 25-minute focus timer |
| Right-click → Rock Paper Scissors 🪨 | Play a quick game against Pip |
| Right-click → Clear History | Wipe this session's conversation memory |
| Right-click → Rename | Rename Pip |

### Clipboard Watcher

When you copy text longer than 30 characters, Pip pops up and offers to explain it.
Left-click Pip within ~10 seconds to open the chat with the clipboard content pre-filled.
Pip won't interrupt you if she's already mid-conversation.

### Typing-Aware Idle

If no keyboard activity is detected for **20 minutes**, Pip pops up with a break reminder.
This resets after each reminder so it doesn't spam. Requires pynput to be installed and
have keyboard access. If pynput fails to start, the feature silently disables itself.

### Active Window Watcher

Every 30 seconds Pip checks the active window title (via `xdotool`) and, with 35% chance,
reacts to what you're doing — browser, coding, terminal, YouTube, Discord, Spotify, etc.
The check only fires when Pip is IDLE so it never interrupts an active conversation.

### Pomodoro Timer

Start a 25-minute focus session from the right-click menu. Pip shows a "you got this"
bubble at the start, then dances and cheers when time's up. Re-selecting the menu item
during a session cancels it.

### Time-Aware Greetings

On the **first launch of each day** Pip greets you based on the time of day:
- 5 am – 12 pm → "Good morning! Ready to code? ☀️"
- 12 pm – 5 pm → "Afternoon slump hitting? I got you."
- 5 pm – 9 pm → "Good evening! Still at it?"
- 9 pm – 5 am → "Still up late? 🌙"

On **subsequent launches the same day** she says "Hey, back already!" instead.

### Streak & Milestones

Pip counts how many consecutive days you've launched her. Milestone messages fire at
**7, 14, 30, 50, 100, and 365** days.

### Birthday

On the anniversary of Pip's creation date (month and day match, but not year-zero),
Pip dances and tells you how many days you've been together. 🎂

### Conversation History

Pip keeps a rolling memory of the last **3 exchanges** (6 messages) within a session.
History is session-only (in-memory). It resets when Pip quits or via **Clear History**.
The `MAX_HISTORY_TURNS = 3` constant in `main.py` controls the cap.

### Mood Reactions

Pip reads the tone of your message and her own reply and switches animation:

| Trigger words | Animation |
|---|---|
| "great", "awesome", "love", "thank", "yay", "cool", "haha" … | Happy bounce + sparkles |
| "dance", "party", "celebrate", "music", "sing" … | Dancing + music notes |
| "boring", "tired", "sleepy", "meh" … | Sleepy eyes + Z's |
| "why", "how", "explain", "what if", "?" … | Thinking (eyes up + dots) |
| *(dragging)* | Surprised wide eyes + speed lines |
| *(default while waiting)* | Thinking |
| *(default on response)* | Talking (mouth animates) |

### Mood Color Tinting

Pip's body color slowly lerps (3% per tick) toward a per-state target color so mood is
readable at a glance without being jarring. IDLE is neutral purple; HAPPY warms up;
SLEEPING cools to blue; DANCING goes pink-purple; DRAGGING pulses vivid violet.

### Mood History Chart

Open **Control Panel → Mood History** to see a colour-coded bar chart of how many times
each mood appeared today. Data is stored in `personality.json` and updates live as you
interact with Pip.

### Daily Journal

At shutdown Pip writes a one-line diary entry recording the day's dominant mood.
Open **Control Panel → Journal** to browse the last 30 entries (newest first).
Entries are stored in `personality.json` and capped at 365 days.

### Custom Quips

Open **Control Panel → Personality** and type your own idle phrases in the **Custom Quips**
box (one per line). They fire alongside the built-in quips on the HAPPY animation.

### Enabling Web Search

Open **Control Panel → Tools & MCP**, check **Enable Web Search**, and click
**Save Tool Settings**. This passes `--allowedTools WebSearch,WebFetch` to the
Claude CLI so Pip can browse the web when answering questions.

### Fun MCP Servers

Copy `mcp_config.example.json` to `mcp_config.json` and enable MCP in
**Control Panel → Tools & MCP** to unlock extra abilities:

| Server | What it does | Requires |
|--------|-------------|---------|
| `time` | Pip knows the current time in any timezone | `pip install uvx` |
| `fetch` | Pip can read any URL/webpage | Node.js |
| `filesystem` | Pip can read files in a directory you specify | Node.js |
| `sequential-thinking` | Step-by-step reasoning for complex problems | Node.js |

Or add your own via the Control Panel — supports both stdio (local command) and HTTP/SSE.

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
| `interactions` | int | Total conversation count |
| `topics` | list[str] | Up to 30 recent topics discussed |
| `mood_log` | list[obj] | Up to 300 recent mood events `{s, t}` for the history chart |
| `streak` | int | Consecutive daily launch count |
| `last_launch` | ISO date | Date of last launch (for streak logic) |
| `custom_quips` | list[str] | User-defined random idle phrases |
| `journal` | list[obj] | Up to 365 daily diary entries `{date, entry, moods}` |
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
| `last_launch_date` | `""` | ISO date of last launch (for daily greeting) |
| `x` / `y` | bottom-right | Saved window position |

---

## TODO — Features to Add

- [ ] **Tray icon** — system tray icon with quick-chat popup and show/hide toggle
- [ ] **Voice output** — TTS via `espeak` / `pyttsx3` / `festival` for spoken responses
- [ ] **Voice input** — microphone button using `SpeechRecognition` or `whisper`
- [ ] **Multiple characters** — switch between different pixel-art skins
- [ ] **Notification hooks** — Pip comments on desktop notifications (calendar events, mail, etc.)
- [ ] **Screen-aware Pip** — Pip moves out of the way of full-screen windows
- [x] **Mini-games** — Rock-Paper-Scissors from the right-click menu
- [x] **Custom quips** — user-editable list of random idle phrases in the Control Panel
- [ ] **Theme editor** — change Pip's color palette in the control panel
- [ ] **Startup on login** — add a `.desktop` autostart entry
- [ ] **Multiple bubble styles** — round, square, thought-bubble variants
- [ ] **Wayland support** — test and fix `wl_surface` layering for Wayland compositors
- [ ] **Export / import personality** — share `personality.json` between machines
- [ ] **Streaming responses** — show Claude's reply word-by-word as it arrives

---

## TODO — Optimizations

- [ ] **Dirty-rect repaints** — only repaint the region that actually changed
- [ ] **Pre-rasterize frames** — cache each animation frame to a `QPixmap` at startup
- [x] **Adaptive frame rate** — IDLE animation advances only every 4th tick (~2 fps); active states run at full 8 fps
- [ ] **Background worker pool** — reuse a single `QThread` instead of a new one per request
- [ ] **Subprocess warm-up** — keep Claude process warm to avoid cold-start latency
- [ ] **Debounce idle reschedule** — avoid restarting `_idle_timer` on rapid settings changes
- [ ] **Bubble text caching** — cache laid-out lines so `_update_geometry` only re-runs on text change
- [ ] **Reduce QSettings writes** — batch position saves; currently writes on every mouseRelease
- [ ] **Lazy-import control panel** — import `control_panel.py` only when first opened
