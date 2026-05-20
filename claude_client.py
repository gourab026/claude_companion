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

from PyQt6.QtCore import QThread, pyqtSignal

# ── File logger (never printed to console, always available for debugging) ────
_LOG_FILE = os.path.join(os.path.expanduser("~"), ".pip-companion.log")
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
_handler = logging.handlers.RotatingFileHandler(
    _LOG_FILE,
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_handler.setFormatter(_fmt)
_handler.setLevel(logging.DEBUG)

# Root logger: NullHandler so third-party libraries don't accidentally emit
logging.getLogger().addHandler(logging.NullHandler())

# Package logger carries our RotatingFileHandler
_pkg_log = logging.getLogger("pip")
_pkg_log.setLevel(logging.DEBUG)
_pkg_log.addHandler(_handler)
_pkg_log.propagate = False

log = logging.getLogger(__name__)


class ClaudeWorker(QThread):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

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
            "--output-format", "text",
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

            log.debug("rc=%d | stdout=%r | stderr=%r",
                      result.returncode,
                      result.stdout[:300],
                      result.stderr[:300])

            if result.returncode == 0:
                out = result.stdout.strip()
                self.response_ready.emit(out or "…")
            else:
                err = (result.stderr.strip()
                       or f"claude exited with code {result.returncode}")
                log.error("claude failed: %s", err)
                self.error_occurred.emit(err)

        except subprocess.TimeoutExpired:
            log.error("claude timed out after 60s")
            self.error_occurred.emit("Timed out — Claude took too long to respond.")
        except FileNotFoundError:
            log.error("claude binary not found: %s", claude_bin)
            self.error_occurred.emit(
                "'claude' not found. Is Claude Code installed and on your PATH?"
            )
        except Exception as exc:
            log.exception("unexpected error in ClaudeWorker")
            self.error_occurred.emit(str(exc))
