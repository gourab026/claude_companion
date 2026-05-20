# Pip — Pixel-Art Desktop Companion

A transparent, always-on-top desktop companion for Linux that lives on your screen,
talks to you through the Claude Code CLI, and develops a personality over time.
**No Anthropic API key required** — Pip uses your existing Claude Code session.

---

## Features

- Pixel-art animated character (idle bob, talking, happy, thinking, sleeping, dancing)
- AI-powered conversation via local `claude` CLI
- Personality that drifts and grows with every interaction
- Random idle events (dance, sleep, quips, random thoughts)
- Persistent speech bubbles
- Draggable and always-on-top
- Control panel for personality, tools, MCP servers, and settings
- Web search support via `--allowedTools`
- Custom MCP server connections (stdio and HTTP/SSE)

---

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                     User Desktop                        │
│                                                         │
│   ┌──────────────┐     click / drag / right-click       │
│   │  Pip Window  │ ◄────────────────────────────────    │
│   │ (transparent │                                       │
│   │  QWidget)    │  paintEvent clears to transparent,   │
│   │              │  then CharacterRenderer draws        │
│   │    [Pip]     │  directly into the window painter.   │
│   └──────┬───────┘                                       │
│          │ left-click                                    │
│          ▼                                               │
│   ┌──────────────┐    ┌────────────────────────────┐    │
│   │  Chat input  │───►│      ClaudeWorker           │    │
│   │  (QDialog)   │    │  (QThread)                  │    │
│   └──────────────┘    │                             │    │
│                       │  subprocess.run(            │    │
│   ┌──────────────┐    │    "claude -p"              │    │
│   │ Speech Bubble│◄───│    --model ...              │    │
│   │ (top-level   │    │    --system-prompt ...      │    │
│   │  QWidget)    │    │    --allowedTools ...       │    │
│   └──────────────┘    │    --mcp-config ...         │    │
│                       │  )                          │    │
│                       └────────────────────────────┘    │
│                                                         │
│   personality.json  ←──  Personality class              │
│   mcp_config.json   ←──  Control Panel MCP tab          │
│   QSettings         ←──  Control Panel Settings tab     │
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
│
├── character.py       CharacterRenderer — pure drawing class (not a QWidget).
│                      Holds animation state machine + frame counters.
│                      Called by CompanionWindow.paintEvent.
│
├── personality.py     Personality — loads/saves personality.json.
│                      Tracks mood, traits, interaction count, topics.
│                      Generates the system prompt passed to Claude.
│
├── claude_client.py   ClaudeWorker (QThread) — runs `claude -p` in background.
│                      Supports --allowedTools and --mcp-config flags.
│                      Emits response_ready or error_occurred signals.
│
├── bubble.py          BubbleWindow — separate top-level transparent QWidget.
│                      Draws a rounded-rect speech bubble with a tail.
│                      Auto-sizes to text, auto-hides after a timer.
│
├── control_panel.py   ControlPanel QWidget with 4 tabs:
│                        Personality — name, traits, mood, topics, reset
│                        Tools & MCP — web search toggle, MCP server manager
│                        Settings    — model, idle interval, position reset
│                        About       — help text
│                      McpServerDialog — add/edit stdio or HTTP MCP servers.
│
├── personality.json   Auto-created on first run. Stores name, mood,
│                      humor/playfulness/helpfulness, interaction count,
│                      topics list, and creation date.
│
├── mcp_config.json    Auto-created when you add an MCP server via the
│                      Control Panel. Passed to `claude --mcp-config`.
│
└── requirements.txt   PyQt6>=6.4.0
```

---

## Installation

```bash
# 1. Install Python dependency
pip install PyQt6

# 2. Make sure Claude Code CLI is installed and authenticated
claude --version     # should print a version number
claude -p "hi"       # should return a response

# 3. Run
cd /path/to/companion
python main.py
```

> A compositor (picom, KWin, Mutter, etc.) must be running for transparency to work.
> On bare X11 without a compositor, the window background will appear black.

---

## Usage

| Action | Result |
|--------|--------|
| Left-click Pip | Open chat input |
| Right-click Pip | Context menu |
| Drag Pip | Move to any screen position (saved on release) |
| Right-click → Control Panel | Open settings, personality editor, MCP config |
| Right-click → Rename | Rename Pip |

### Enabling Web Search

Open **Control Panel → Tools & MCP**, check **Enable Web Search**, and click
**Save Tool Settings**. This passes `--allowedTools WebSearch,WebFetch` to the
Claude CLI so Pip can browse the web when answering questions.

### Adding an MCP Server

1. Open **Control Panel → Tools & MCP**
2. Check **Enable MCP servers**
3. Click **Add Server**
4. Choose **stdio** (local command) or **HTTP/SSE** (remote URL)
5. Fill in the command/URL and optional args/env
6. Click **OK**, then **Save MCP Settings**

Example stdio server (filesystem access):
```
Name:    filesystem
Command: npx
Args:    -y @modelcontextprotocol/server-filesystem /home/user/docs
```

Example HTTP server:
```
Name: my-api
URL:  http://localhost:3000/sse
```

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

- [ ] **Tray icon** — system tray icon with quick-chat popup and show/hide toggle
- [ ] **Voice output** — TTS via `espeak` / `pyttsx3` / `festival` for spoken responses
- [ ] **Voice input** — microphone button using `SpeechRecognition` or `whisper`
- [ ] **Multiple characters** — switch between different pixel-art skins
- [ ] **Conversation history** — multi-turn memory within a session (not just personality topics)
- [ ] **Mood reactions** — Pip reacts visually when certain keywords appear (e.g. "great!" → HAPPY)
- [ ] **Notification hooks** — Pip comments on desktop notifications (calendar events, mail, etc.)
- [ ] **Screen-aware Pip** — Pip moves out of the way of full-screen windows
- [ ] **Mini-games** — click to play rock-paper-scissors or trivia against Pip
- [ ] **Custom quips** — user-editable list of random idle phrases
- [ ] **Theme editor** — change Pip's color palette in the control panel
- [ ] **Startup on login** — add a `.desktop` autostart entry
- [ ] **Multiple bubble styles** — round, square, thought-bubble variants
- [ ] **Wayland support** — test and fix `wl_surface` layering for Wayland compositors
- [ ] **Export / import personality** — share `personality.json` between machines
- [ ] **Streaming responses** — show Claude's reply word-by-word as it arrives

---

## TODO — Optimizations

- [ ] **Dirty-rect repaints** — only repaint the region that actually changed (currently repaints entire canvas every frame)
- [ ] **Pre-rasterize frames** — render each animation frame to a `QPixmap` once at startup and blit from cache instead of re-running draw calls every tick
- [ ] **Adaptive frame rate** — slow animation timer to ~2 fps when idle/sleeping, speed up to 8 fps only during active states
- [ ] **Background worker pool** — reuse a single `QThread` instead of creating a new `ClaudeWorker` per request
- [ ] **Subprocess warm-up** — pre-launch the Claude process and keep stdin open to avoid cold-start latency on every message
- [ ] **Debounce idle reschedule** — avoid restarting `_idle_timer` redundantly on rapid settings changes
- [ ] **Bubble text caching** — cache the laid-out lines so `_update_geometry` only re-runs when text changes, not on every `show_text` call
- [ ] **Memory cap on topics list** — currently capped at 30 but no deduplication by semantic similarity; add fuzzy dedup
- [ ] **Reduce QSettings writes** — batch position saves; currently writes on every mouseRelease even if position didn't change
- [ ] **Lazy-import control panel** — import `control_panel.py` only when the user first opens it to cut startup time
