import subprocess
from PyQt6.QtCore import QThread, pyqtSignal


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
        self._allowed_tools = allowed_tools   # comma-separated, e.g. "WebSearch,WebFetch"
        self._mcp_config    = mcp_config      # path to mcp_config.json

    def run(self):
        cmd = [
            "claude", "-p",
            "--output-format", "text",
            "--model", self._model,
            "--system-prompt", self._system_prompt,
        ]

        if self._allowed_tools:
            cmd += ["--allowedTools", self._allowed_tools]

        if self._mcp_config:
            cmd += ["--mcp-config", self._mcp_config]

        cmd.append(self._prompt)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                self.response_ready.emit(result.stdout.strip())
            else:
                err = result.stderr.strip() or "Claude returned an error."
                self.error_occurred.emit(err)
        except subprocess.TimeoutExpired:
            self.error_occurred.emit("Timed out waiting for a response...")
        except FileNotFoundError:
            self.error_occurred.emit("'claude' command not found. Is Claude Code installed?")
        except Exception as e:
            self.error_occurred.emit(str(e))
