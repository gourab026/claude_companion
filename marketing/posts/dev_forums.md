# Dev Forums Posts

Targets: dev.to, Hacker News (Show HN), Hashnode, Lobsters

---

## dev.to / Hashnode Article

**Title:** I built an open-source AI desktop companion powered by Claude Code CLI — here's how it works

**Tags:** `python` `opensource` `linux` `ai`

---

After a few months of side-project work, I'm excited to share **Pip** — an animated pixel-art desktop companion for Linux that uses the Claude Code CLI as its AI backend instead of the raw Anthropic API.

Here's what that means in practice, and why it made the architecture interesting.

### The core idea: `claude -p` as a subprocess

Instead of importing the Anthropic SDK and managing API keys, Pip does this:

```python
import subprocess

result = subprocess.run(
    ["claude", "-p", prompt, "--output-format", "text"],
    capture_output=True, text=True, timeout=60
)
response = result.stdout.strip()
```

This approach gives Pip a few things for free:
- **No API key management** — it uses the user's existing authenticated Claude Code session
- **Web search** — Claude Code has it, so Pip has it
- **MCP servers** — any MCP server the user has configured in Claude Code is automatically available to Pip

The tradeoff is latency (subprocess overhead) and no streaming — but for a desktop companion that sends short conversational messages, this is fine.

### Keeping the UI responsive: QThread workers

Every Claude call runs in a `ClaudeWorker(QThread)`:

```python
class ClaudeWorker(QThread):
    result = pyqtSignal(str)
    error  = pyqtSignal(str)

    def __init__(self, prompt: str):
        super().__init__()
        self._prompt = prompt

    def run(self):
        try:
            out = subprocess.run(
                ["claude", "-p", self._prompt, "--output-format", "text"],
                capture_output=True, text=True, timeout=90
            ).stdout.strip()
            self.result.emit(out)
        except Exception as e:
            self.error.emit(str(e))
```

Workers are stored as instance attributes (`self._worker`, `self._song_fact_worker`, etc.) — not local variables — to prevent Python's GC from destroying them mid-run and triggering a SIGABRT.

In `closeEvent`, all running workers are explicitly stopped:

```python
def closeEvent(self, event):
    for w in [self._worker, self._haiku_worker, self._song_fact_worker, ...]:
        if w and w.isRunning():
            w.quit()
            w.wait(2000)
    event.accept()
```

### The personality system

Pip's personality lives in `personality.json` — a flat JSON file that tracks:

- `interactions` — total conversation count
- `mood` — current mood string
- `humor` / `playfulness` — float values that drift ±0.05 every 5 interactions
- `topics` — last 20 topics discussed
- `user_profile` — work type, interests, communication style, check-in history
- `journal` — daily entries about the user
- `achievements_unlocked` — milestone list
- `vocabulary` — words the user has taught Pip

On every AI call, `get_system_prompt()` injects the relevant state:

```python
def get_system_prompt(self) -> str:
    level = self._relationship_level()
    profile = self._data.get("user_profile", {})
    vocab = list(profile.get("vocabulary", {}).keys())[:5]

    return f"""You are Pip, a {level} AI desktop companion.
Mood: {self._data['mood']}. Humor: {self._data['humor']:.2f}.
User's work type: {profile.get('work_type', 'unknown')}.
Topics we've discussed: {', '.join(self._data.get('topics', [])[-5:])}.
Words they've taught you: {', '.join(vocab)}.
Keep replies under 2 sentences. Be {self._tone_for_level(level)}."""
```

Writes are atomic: write to `.tmp`, then `os.replace()` to prevent corruption on crash.

### Speech bubble priority queue

Pip shows speech bubbles above her head. When multiple events fire simultaneously (music change + wellness reminder + AI reply), they need to queue without overlapping:

```python
BUBBLE_LOW    = 0  # ambient chatter — dropped if bubble active
BUBBLE_NORMAL = 1  # wellness / events — queued
BUBBLE_HIGH   = 2  # AI replies / user actions — queued at front

def _show_bubble(self, text, style=SPEECH, priority=BUBBLE_NORMAL):
    if self._bubble.isVisible():
        if priority == BUBBLE_LOW:
            return  # drop silently
        self._bubble_queue.append((priority, text, style))
        self._bubble_queue.sort(key=lambda x: x[0], reverse=True)
        if len(self._bubble_queue) > 3:
            self._bubble_queue.pop()  # drop oldest low-priority
    else:
        self._show_bubble_now(text, style)
```

When a bubble closes, `bubble_closed` signal drains the queue.

### Open source

GitHub: https://github.com/gourab026/claude_companion
License: Polyform Noncommercial 1.0

I'd love feedback on the architecture, especially around the threading model and the personality system. What would you build differently?

---

## Hacker News (Show HN)

**Title:** Show HN: Pip – open-source AI desktop companion for Linux using Claude Code CLI

**URL:** https://github.com/gourab026/claude_companion

**Comment:**

Pip is a PyQt6 desktop app that renders a pixel-art character on your screen. Instead of the Anthropic API, it uses `claude -p` subprocess calls — so if you already use Claude Code, no additional setup is needed.

Key technical bits: QThread workers for non-blocking AI calls, a priority speech bubble queue (LOW drops if busy, NORMAL queues, HIGH jumps to front), atomic JSON personality saves, and a relationship system where Pip's system prompt dynamically reflects your interaction history.

Linux only for now. MIT wasn't quite the right license since I don't want commercial use without permission, so it's Polyform Noncommercial 1.0.

Feedback welcome, particularly on the threading model.

---

## Lobsters

**Title:** Pip: pixel-art AI desktop companion for Linux (PyQt6 + Claude Code CLI)

**Tags:** `python` `linux` `ai` `gui` `open-source`

**Comment:**

Personal project I've been building with Claude Code. Uses the CLI as its AI backend rather than the API — `subprocess.run(["claude", "-p", prompt])` — which means no API key and web search comes for free.

Technically interesting bits: QThread worker pool with explicit lifecycle management in closeEvent (learned this the hard way after repeated SIGABRTs from GC'd threads), a three-tier bubble priority queue, and a personality system that dynamically generates the system prompt from a JSON state file tracking 500+ interactions worth of context.

Source: https://github.com/gourab026/claude_companion
