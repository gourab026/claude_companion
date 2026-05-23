"""
ClaudeWorker — runs `claude -p` in a background QThread.

Key design notes:
- Prompt is fed via stdin (not as a positional argument) because
  --allowedTools is variadic (<tools...>) and greedily consumes every
  remaining argv token, swallowing the prompt and causing the error:
    "Input must be provided either through stdin or as a prompt argument"
- start_new_session=True isolates the child from Qt's SIGCHLD handler,
  which would otherwise race with subprocess.communicate().
- cwd=HOME avoids Claude Code picking up project CLAUDE.md from the
  companion directory.
- --no-session-persistence is the correct flag for scripted/automated use.
- All output is logged to ~/.pip-companion.log for debugging.
"""

import logging
import logging.handlers
import os
import shutil
import subprocess
import sys

from PyQt6.QtCore import QThread, pyqtSignal

# ── ANSI color codes (terminal only) ─────────────────────────────────────────
_COLORS = {
    'DEBUG':    '\033[36m',   # cyan
    'INFO':     '\033[32m',   # green
    'WARNING':  '\033[33m',   # yellow
    'ERROR':    '\033[31m',   # red
    'CRITICAL': '\033[35m',   # magenta
}
_RESET = '\033[0m'
_BOLD  = '\033[1m'
_BLUE  = '\033[34m'


class ColoredFormatter(logging.Formatter):
    """ANSI-colored formatter for StreamHandler (terminal only)."""

    def format(self, record):
        # Work on a copy so we don't mutate the LogRecord for other handlers
        record = logging.makeLogRecord(record.__dict__)
        color = _COLORS.get(record.levelname, '')
        record.levelname = f"{color}{_BOLD}{record.levelname:<8}{_RESET}"
        record.name = f"{_BLUE}{record.name}{_RESET}"
        return super().format(record)


# ── File logger — structured plain text, no ANSI ─────────────────────────────
_LOG_FILE = os.path.join(os.path.expanduser("~"), ".pip-companion.log")
_file_fmt = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_file_handler = logging.handlers.RotatingFileHandler(
    _LOG_FILE,
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_file_handler.setFormatter(_file_fmt)
_file_handler.setLevel(logging.DEBUG)

# ── Stream (terminal) handler — colored ───────────────────────────────────────
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_fmt = ColoredFormatter(
    fmt="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
_stream_handler.setFormatter(_stream_fmt)
_stream_handler.setLevel(logging.DEBUG)

# Root logger: NullHandler so third-party libraries don't accidentally emit
logging.getLogger().addHandler(logging.NullHandler())

# Package logger carries both handlers
_pkg_log = logging.getLogger("pip")
_pkg_log.setLevel(logging.DEBUG)
_pkg_log.addHandler(_file_handler)
_pkg_log.addHandler(_stream_handler)
_pkg_log.propagate = False

log = logging.getLogger("pip.claude")


class ClaudeWorker(QThread):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    usage_ready    = pyqtSignal(int, int)   # input_tokens, output_tokens

    def __init__(
        self,
        prompt: str,
        system_prompt: str,
        *,
        model: str = "claude-sonnet-4-6",
        allowed_tools: str | None = None,
        mcp_config: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._prompt        = prompt
        self._system_prompt = system_prompt
        self._model         = model
        self._allowed_tools = allowed_tools
        self._mcp_config    = mcp_config

    def run(self):
        # Resolve full binary path so PATH issues inside QThread don't matter
        claude_bin = shutil.which("claude") or "claude"

        cmd = [
            claude_bin, "-p",
            "--output-format", "json",
            "--model", self._model,
            "--no-session-persistence",   # correct for scripted / automated use
            "--system-prompt", self._system_prompt,
        ]

        if self._allowed_tools:
            cmd += ["--allowedTools", self._allowed_tools]

        if self._mcp_config:
            cmd += ["--mcp-config", self._mcp_config]

        # ── Prompt via stdin, NOT as a positional argument ────────────────────
        # --allowedTools is variadic (<tools...>) and greedily consumes every
        # remaining argv token, so appending the prompt after it causes the CLI
        # to treat the prompt text as another tool name and return:
        #   "Input must be provided either through stdin or as a prompt argument"
        # Passing via stdin (input=) sidesteps all positional-arg parsing issues.

        env = os.environ.copy()
        env.setdefault("HOME", os.path.expanduser("~"))

        log.debug("cmd: %s", cmd)
        log.debug("stdin: %r", self._prompt[:120])

        import time as _time
        _t0 = _time.time()
        log.info("Claude call started (model=%s, elapsed=0ms)", self._model)

        try:
            result = subprocess.run(
                cmd,
                input=self._prompt,            # ← prompt via stdin
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                cwd=os.path.expanduser("~"),
                env=env,
                start_new_session=True,
            )

            elapsed_ms = int((_time.time() - _t0) * 1000)
            log.debug("rc=%d | stdout=%r | stderr=%r",
                      result.returncode,
                      result.stdout[:300],
                      result.stderr[:300])

            if result.returncode == 0:
                raw = result.stdout.strip()
                text = raw
                input_tok = output_tok = 0
                try:
                    import json as _json
                    data = _json.loads(raw)
                    text = data.get("result", raw).strip()
                    usage = data.get("usage", {})
                    input_tok  = usage.get("input_tokens", 0)
                    output_tok = usage.get("output_tokens", 0)
                except Exception:
                    pass  # fall back to raw text if JSON parse fails
                log.info(
                    "Claude response received (elapsed=%dms, chars=%d, in=%d, out=%d)",
                    elapsed_ms, len(text), input_tok, output_tok,
                )
                if input_tok or output_tok:
                    self.usage_ready.emit(input_tok, output_tok)
                self.response_ready.emit(text or "…")
            else:
                err = (result.stderr.strip()
                       or f"claude exited with code {result.returncode}")
                log.error("Claude call failed (elapsed=%dms): %s", elapsed_ms, err)
                self.error_occurred.emit(err)

        except subprocess.TimeoutExpired:
            log.error("Claude call timed out after 60s")
            self.error_occurred.emit("Timed out — Claude took too long to respond.")
        except FileNotFoundError:
            log.error("claude binary not found: %s", claude_bin)
            self.error_occurred.emit(
                "'claude' not found. Is Claude Code installed and on your PATH?"
            )
        except Exception as exc:
            log.exception("Unexpected error in ClaudeWorker")
            self.error_occurred.emit(str(exc))
