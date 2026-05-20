import json
import os
from datetime import datetime as _dt

from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QSlider, QPushButton,
    QGroupBox, QFormLayout, QComboBox, QSpinBox,
    QTextEdit, QMessageBox, QCheckBox,
    QListWidget, QListWidgetItem, QDialog,
    QDialogButtonBox, QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt, QSettings, pyqtSignal

from personality import Personality, DEFAULTS


class ControlPanel(QWidget):
    settings_changed = pyqtSignal()

    def __init__(self, personality: Personality, settings: QSettings,
                 mcp_config_path: str, parent=None):
        super().__init__(parent)
        self._p   = personality
        self._s   = settings
        self._mcp = mcp_config_path
        self.setWindowTitle("Pip — Control Panel")
        self.setMinimumWidth(440)
        self.setWindowFlags(Qt.WindowType.Window)

        tabs = QTabWidget()
        tabs.addTab(self._personality_tab(), "Personality")
        tabs.addTab(self._mood_tab(),        "Mood History")
        tabs.addTab(self._tools_tab(),       "Tools & MCP")
        tabs.addTab(self._settings_tab(),    "Settings")
        tabs.addTab(self._about_tab(),       "About")

        root = QVBoxLayout(self)
        root.addWidget(tabs)

    # ═══════════════════════════════════════════ Personality tab ═════════════

    def _personality_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)

        # Identity
        id_box = QGroupBox("Identity")
        id_form = QFormLayout(id_box)
        self._name_edit = QLineEdit()
        id_form.addRow("Name:", self._name_edit)
        lo.addWidget(id_box)

        # Stats
        stats_box = QGroupBox("Stats")
        sf = QFormLayout(stats_box)
        self._interactions_lbl = QLabel()
        self._mood_lbl         = QLabel()
        self._created_lbl      = QLabel()
        sf.addRow("Total interactions:", self._interactions_lbl)
        sf.addRow("Current mood:",       self._mood_lbl)
        sf.addRow("Companion since:",    self._created_lbl)
        lo.addWidget(stats_box)

        # Traits
        traits_box = QGroupBox("Personality Traits")
        tf = QFormLayout(traits_box)
        self._humor_s   = _slider()
        self._playful_s = _slider()
        self._helpful_s = _slider()
        self._humor_l   = QLabel()
        self._playful_l = QLabel()
        self._helpful_l = QLabel()
        for s, l in [(self._humor_s, self._humor_l),
                     (self._playful_s, self._playful_l),
                     (self._helpful_s, self._helpful_l)]:
            s.valueChanged.connect(lambda v, lb=l: lb.setText(f"{v}%"))
        tf.addRow("Humor:",       _row(self._humor_s,   self._humor_l))
        tf.addRow("Playfulness:", _row(self._playful_s, self._playful_l))
        tf.addRow("Helpfulness:", _row(self._helpful_s, self._helpful_l))
        lo.addWidget(traits_box)

        # Topics
        topics_box = QGroupBox("Topics Pip Remembers")
        tv = QVBoxLayout(topics_box)
        self._topics_view = QTextEdit()
        self._topics_view.setReadOnly(True)
        self._topics_view.setMaximumHeight(80)
        tv.addWidget(self._topics_view)
        lo.addWidget(topics_box)

        # Buttons
        btns = QHBoxLayout()
        save_btn  = QPushButton("Save Changes")
        reset_btn = QPushButton("Reset Personality")
        reset_btn.setStyleSheet("color: #c0392b;")
        save_btn.clicked.connect(self._save_personality)
        reset_btn.clicked.connect(self._reset_personality)
        btns.addWidget(save_btn)
        btns.addWidget(reset_btn)
        lo.addLayout(btns)
        lo.addStretch()
        return w

    # ═══════════════════════════════════════════ Mood History tab ════════════

    def _mood_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.addWidget(QLabel("Today's mood activity (updates when Pip reacts):"))
        self._mood_chart = MoodChart(self._p._data.get("mood_log", []))
        lo.addWidget(self._mood_chart)
        lo.addStretch()
        return w

    # ═══════════════════════════════════════════ Tools & MCP tab ═════════════

    def _tools_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)

        # Built-in tools
        tools_box = QGroupBox("Built-in Tool Permissions")
        tlo = QVBoxLayout(tools_box)

        self._web_search_cb = QCheckBox("Enable Web Search  (WebSearch + WebFetch)")
        self._web_search_cb.setToolTip(
            "Passes --allowedTools WebSearch,WebFetch to the Claude CLI.\n"
            "Pip can then look things up on the web when answering questions."
        )
        self._web_search_cb.setChecked(
            "WebSearch" in self._s.value("allowed_tools", "", type=str)
        )
        tlo.addWidget(self._web_search_cb)

        self._bash_cb = QCheckBox("Enable Bash tool  (lets Pip run shell commands)")
        self._bash_cb.setToolTip(
            "Passes Bash in --allowedTools. Use only if you trust the model\n"
            "to execute commands on your machine."
        )
        self._bash_cb.setChecked(
            "Bash" in self._s.value("allowed_tools", "", type=str)
        )
        tlo.addWidget(self._bash_cb)

        save_tools_btn = QPushButton("Save Tool Settings")
        save_tools_btn.clicked.connect(self._save_tools)
        tlo.addWidget(save_tools_btn)
        lo.addWidget(tools_box)

        # MCP servers
        mcp_box = QGroupBox("MCP Servers")
        mlo = QVBoxLayout(mcp_box)

        self._use_mcp_cb = QCheckBox("Enable MCP servers")
        self._use_mcp_cb.setChecked(self._s.value("use_mcp", False, type=bool))
        mlo.addWidget(self._use_mcp_cb)

        self._mcp_list = QListWidget()
        self._mcp_list.setMaximumHeight(140)
        mlo.addWidget(self._mcp_list)

        mcp_btns = QHBoxLayout()
        add_btn  = QPushButton("Add Server")
        edit_btn = QPushButton("Edit")
        del_btn  = QPushButton("Remove")
        add_btn.clicked.connect(self._add_mcp_server)
        edit_btn.clicked.connect(self._edit_mcp_server)
        del_btn.clicked.connect(self._remove_mcp_server)
        for b in [add_btn, edit_btn, del_btn]:
            mcp_btns.addWidget(b)
        mlo.addLayout(mcp_btns)

        # Raw JSON viewer
        mlo.addWidget(QLabel("Raw mcp_config.json:"))
        self._mcp_json_view = QTextEdit()
        self._mcp_json_view.setReadOnly(True)
        self._mcp_json_view.setMaximumHeight(100)
        mlo.addWidget(self._mcp_json_view)

        save_mcp_btn = QPushButton("Save MCP Settings")
        save_mcp_btn.clicked.connect(self._save_mcp)
        mlo.addWidget(save_mcp_btn)

        lo.addWidget(mcp_box)
        lo.addStretch()
        self._reload_mcp_list()
        return w

    # ═══════════════════════════════════════════ Settings tab ════════════════

    def _settings_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)

        model_box = QGroupBox("AI Model")
        mf = QFormLayout(model_box)
        self._model_combo = QComboBox()
        self._model_combo.addItems([
            "claude-sonnet-4-6",
            "claude-opus-4-7",
            "claude-haiku-4-5",
        ])
        idx = self._model_combo.findText(self._s.value("model", "claude-sonnet-4-6"))
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        mf.addRow("Model:", self._model_combo)
        lo.addWidget(model_box)

        idle_box = QGroupBox("Random Event Interval")
        idf = QFormLayout(idle_box)
        self._idle_min = QSpinBox()
        self._idle_min.setRange(10, 300); self._idle_min.setSuffix(" sec")
        self._idle_min.setValue(self._s.value("idle_min", 30, type=int))
        self._idle_max = QSpinBox()
        self._idle_max.setRange(30, 600); self._idle_max.setSuffix(" sec")
        self._idle_max.setValue(self._s.value("idle_max", 90, type=int))
        idf.addRow("Minimum:", self._idle_min)
        idf.addRow("Maximum:", self._idle_max)
        lo.addWidget(idle_box)

        pos_box = QGroupBox("Window Position")
        plo = QVBoxLayout(pos_box)
        reset_pos = QPushButton("Reset to Default Position")
        reset_pos.clicked.connect(self._reset_position)
        plo.addWidget(reset_pos)
        lo.addWidget(pos_box)

        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._save_settings)
        lo.addWidget(save_btn)
        lo.addStretch()
        return w

    # ═══════════════════════════════════════════ About tab ═══════════════════

    def _about_tab(self):
        w = QWidget()
        lo = QVBoxLayout(w)
        lbl = QLabel(
            "<h2>Pip — Desktop Companion</h2>"
            "<p>A pixel-art AI companion powered by the <b>Claude Code CLI</b>.<br>"
            "No API key needed — uses your local Claude Code session.</p>"
            "<hr>"
            "<p><b>Controls</b><br>"
            "&nbsp;• Left-click → chat &nbsp;• Right-click → menu &nbsp;• Drag → move</p>"
            "<p><b>Personality</b><br>"
            "Pip tracks topics, drifts in humor &amp; playfulness over time,<br>"
            "and adapts her mood based on your conversations.</p>"
            "<p><b>Tools</b><br>"
            "Enable Web Search so Pip can look things up.<br>"
            "Add MCP servers for custom integrations.</p>"
        )
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        lo.addWidget(lbl)
        lo.addStretch()
        return w

    # ═══════════════════════════════════════════ Refresh (public) ════════════

    def refresh(self):
        d = self._p._data
        self._name_edit.setText(d["name"])
        self._interactions_lbl.setText(str(d["interactions"]))
        self._mood_lbl.setText(d["mood"].capitalize())
        self._created_lbl.setText(d.get("created", "?")[:10])
        self._humor_s.setValue(int(d["humor"]       * 100))
        self._playful_s.setValue(int(d["playfulness"] * 100))
        self._helpful_s.setValue(int(d["helpfulness"] * 100))
        topics = d.get("topics", [])
        self._topics_view.setPlainText(", ".join(topics) if topics else "(none yet)")
        self._mood_chart.set_log(d.get("mood_log", []))
        self._reload_mcp_list()

    # ═══════════════════════════════════════════ Personality actions ══════════

    def _save_personality(self):
        name = self._name_edit.text().strip()
        if name:
            self._p._data["name"] = name
        self._p._data["humor"]       = self._humor_s.value()   / 100
        self._p._data["playfulness"] = self._playful_s.value() / 100
        self._p._data["helpfulness"] = self._helpful_s.value() / 100
        self._p.save()
        self.settings_changed.emit()
        self.refresh()
        QMessageBox.information(self, "Saved", "Personality updated!")

    def _reset_personality(self):
        if QMessageBox.question(
            self, "Reset",
            "Wipe all of Pip's memories and traits?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            from personality import DATA_FILE
            if os.path.exists(DATA_FILE):
                os.remove(DATA_FILE)
            self._p.load()
            self.refresh()
            self.settings_changed.emit()

    # ═══════════════════════════════════════════ Tools actions ════════════════

    def _save_tools(self):
        tools = []
        if self._web_search_cb.isChecked():
            tools += ["WebSearch", "WebFetch"]
        if self._bash_cb.isChecked():
            tools.append("Bash")
        self._s.setValue("allowed_tools", ",".join(tools))
        self.settings_changed.emit()
        QMessageBox.information(self, "Saved", "Tool settings saved!")

    def _save_mcp(self):
        self._s.setValue("use_mcp", self._use_mcp_cb.isChecked())
        self.settings_changed.emit()
        QMessageBox.information(self, "Saved", "MCP settings saved!")

    # ═══════════════════════════════════════════ MCP server management ════════

    def _load_mcp_data(self) -> dict:
        if os.path.exists(self._mcp):
            try:
                with open(self._mcp) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"mcpServers": {}}

    def _save_mcp_data(self, data: dict):
        with open(self._mcp, "w") as f:
            json.dump(data, f, indent=2)

    def _reload_mcp_list(self):
        data = self._load_mcp_data()
        self._mcp_list.clear()
        for name, cfg in data.get("mcpServers", {}).items():
            kind = "http" if "url" in cfg else "stdio"
            item = QListWidgetItem(f"[{kind}]  {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._mcp_list.addItem(item)
        self._mcp_json_view.setPlainText(json.dumps(data, indent=2))

    def _add_mcp_server(self):
        dlg = McpServerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = self._load_mcp_data()
            name, cfg = dlg.result()
            data["mcpServers"][name] = cfg
            self._save_mcp_data(data)
            self._reload_mcp_list()

    def _edit_mcp_server(self):
        item = self._mcp_list.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        data = self._load_mcp_data()
        cfg  = data["mcpServers"].get(name, {})
        dlg  = McpServerDialog(self, name=name, cfg=cfg)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_name, new_cfg = dlg.result()
            del data["mcpServers"][name]
            data["mcpServers"][new_name] = new_cfg
            self._save_mcp_data(data)
            self._reload_mcp_list()

    def _remove_mcp_server(self):
        item = self._mcp_list.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(
            self, "Remove", f"Remove MCP server '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            data = self._load_mcp_data()
            data["mcpServers"].pop(name, None)
            self._save_mcp_data(data)
            self._reload_mcp_list()

    # ═══════════════════════════════════════════ Settings actions ════════════

    def _save_settings(self):
        if self._idle_min.value() >= self._idle_max.value():
            QMessageBox.warning(self, "Invalid", "Minimum must be less than maximum.")
            return
        self._s.setValue("model",    self._model_combo.currentText())
        self._s.setValue("idle_min", self._idle_min.value())
        self._s.setValue("idle_max", self._idle_max.value())
        self.settings_changed.emit()
        QMessageBox.information(self, "Saved", "Settings saved!")

    def _reset_position(self):
        self._s.remove("x"); self._s.remove("y")
        QMessageBox.information(self, "Done", "Position reset. Restart Pip to apply.")


# ═══════════════════════════════════════ MCP Server dialog ═══════════════════

class McpServerDialog(QDialog):
    def __init__(self, parent=None, name: str = "", cfg: dict = None):
        super().__init__(parent)
        cfg = cfg or {}
        self.setWindowTitle("MCP Server")
        self.setMinimumWidth(360)

        lo = QVBoxLayout(self)

        # Name
        nf = QFormLayout()
        self._name = QLineEdit(name)
        nf.addRow("Server name:", self._name)
        lo.addLayout(nf)

        # Type
        type_box = QGroupBox("Connection type")
        type_lo = QHBoxLayout(type_box)
        self._stdio_rb = QRadioButton("stdio  (local command)")
        self._http_rb  = QRadioButton("HTTP / SSE  (remote URL)")
        bg = QButtonGroup(self)
        bg.addButton(self._stdio_rb); bg.addButton(self._http_rb)
        type_lo.addWidget(self._stdio_rb); type_lo.addWidget(self._http_rb)
        lo.addWidget(type_box)

        # stdio fields
        self._stdio_box = QGroupBox("stdio config")
        sf = QFormLayout(self._stdio_box)
        self._cmd  = QLineEdit(cfg.get("command", ""))
        self._args = QLineEdit(" ".join(cfg.get("args", [])))
        self._env  = QTextEdit()
        self._env.setMaximumHeight(70)
        self._env.setPlaceholderText("KEY=value  (one per line)")
        env_str = "\n".join(f"{k}={v}" for k, v in cfg.get("env", {}).items())
        self._env.setPlainText(env_str)
        sf.addRow("Command:",  self._cmd)
        sf.addRow("Args:",     self._args)
        sf.addRow("Env vars:", self._env)
        lo.addWidget(self._stdio_box)

        # HTTP fields
        self._http_box = QGroupBox("HTTP / SSE config")
        hf = QFormLayout(self._http_box)
        self._url = QLineEdit(cfg.get("url", ""))
        self._url.setPlaceholderText("http://localhost:3000/sse")
        hf.addRow("URL:", self._url)
        lo.addWidget(self._http_box)

        # Detect initial type
        if "url" in cfg:
            self._http_rb.setChecked(True)
        else:
            self._stdio_rb.setChecked(True)

        self._stdio_rb.toggled.connect(self._update_visibility)
        self._update_visibility()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        lo.addWidget(btns)

    def _update_visibility(self):
        self._stdio_box.setVisible(self._stdio_rb.isChecked())
        self._http_box.setVisible(self._http_rb.isChecked())

    def _validate(self):
        if not self._name.text().strip():
            QMessageBox.warning(self, "Error", "Server name is required.")
            return
        if self._stdio_rb.isChecked() and not self._cmd.text().strip():
            QMessageBox.warning(self, "Error", "Command is required for stdio servers.")
            return
        if self._http_rb.isChecked() and not self._url.text().strip():
            QMessageBox.warning(self, "Error", "URL is required for HTTP servers.")
            return
        self.accept()

    def result(self) -> tuple[str, dict]:
        name = self._name.text().strip()
        if self._stdio_rb.isChecked():
            cfg: dict = {"command": self._cmd.text().strip()}
            args = self._args.text().split()
            if args:
                cfg["args"] = args
            env = {}
            for line in self._env.toPlainText().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
            if env:
                cfg["env"] = env
        else:
            cfg = {"url": self._url.text().strip()}
        return name, cfg


# ═══════════════════════════════════════ Mood chart ══════════════════════════

class MoodChart(QWidget):
    _COLORS = {
        "HAPPY":    QColor(255, 215,  50),
        "DANCING":  QColor(200, 120, 240),
        "TALKING":  QColor(110, 200, 140),
        "THINKING": QColor(140, 190, 255),
        "SLEEPING": QColor(180, 210, 255),
    }
    _ORDER = ["HAPPY", "DANCING", "TALKING", "THINKING", "SLEEPING"]

    def __init__(self, mood_log: list, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self._counts: dict[str, int] = {}
        self.set_log(mood_log)

    def set_log(self, mood_log: list):
        today = _dt.now().date().isoformat()
        counts = {k: 0 for k in self._ORDER}
        for entry in mood_log:
            s = entry.get("s", "")
            if entry.get("t", "").startswith(today) and s in counts:
                counts[s] += 1
        self._counts = counts
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if sum(self._counts.values()) == 0:
            p.setPen(QColor(150, 150, 150))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No mood data yet today.\nInteract with Pip to see stats!")
            return

        w, h   = self.width(), self.height()
        pad    = 16
        label_h = 18
        bar_area_h = h - pad * 2 - label_h
        n      = len(self._ORDER)
        slot_w = (w - pad * 2) // n
        bar_w  = max(8, slot_w - 10)
        max_c  = max(self._counts.values()) or 1

        for i, name in enumerate(self._ORDER):
            count  = self._counts[name]
            bar_h  = int(count / max_c * bar_area_h)
            x      = pad + i * slot_w + (slot_w - bar_w) // 2
            y      = pad + bar_area_h - bar_h
            color  = self._COLORS[name]

            if bar_h > 0:
                p.fillRect(x, y, bar_w, bar_h, color)

            p.setPen(QColor(80, 80, 80))
            p.drawText(x, pad + bar_area_h + label_h - 2, name[:4])
            if count:
                p.setPen(QColor(40, 40, 40))
                p.drawText(x + 2, y - 3, str(count))


# ═══════════════════════════════════════ Helpers ═════════════════════════════

def _slider() -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(0, 100)
    s.setFixedWidth(160)
    return s


def _row(slider: QSlider, label: QLabel) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    label.setFixedWidth(36)
    h.addWidget(slider)
    h.addWidget(label)
    return w
