"""
ClaudeWorker — runs `claude -p` in a background QThread.

Key design notes:
- start_new_session=True isolates the child from Qt's installed SIGCHLD
  handler, which would otherwise race with subprocess.communicate() and
  cause non-deterministic "Oops" errors.
- cwd=HOME avoids Claude Code picking up project CLAUDE.md from the
  companion directory and potentially bailing on workspace-trust checks.
- --no-session-persistence is the correct flag for scripted/automated use.
- All output is logged to ~/.pip-companion.log for post-mortem debugging.
"""

import logging
import os
import shutil
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal

# ── File logger (never printed to console, always available for debugging) ────
_LOG_FILE = os.path.join(os.path.expanduser("~"), ".pip-companion.log")
logging.basicConfig(
    filename=_LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
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

        cmd.append(self._prompt)

        # Explicit env: guarantees HOME is set correctly inside the QThread
        env = os.environ.copy()
        env.setdefault("HOME", os.path.expanduser("~"))

        log.debug("cmd: %s", cmd)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                cwd=os.path.expanduser("~"),  # run from HOME, not companion dir
                env=env,
                start_new_session=True,        # ← key: isolate from Qt SIGCHLD handler
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
