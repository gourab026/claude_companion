"""
Google Calendar client — wraps google-api-python-client.

Setup:
  1. Create a Google Cloud project and enable the Calendar API.
  2. Create OAuth 2.0 credentials (Desktop app) and download as credentials.json.
  3. Place the file at ~/.config/pip-companion/gcal_credentials.json
  4. Click "Connect Google Calendar" in Settings — browser opens for OAuth.
     The access token is stored at ~/.config/pip-companion/gcal_token.json.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger("pip.gcal")

CONFIG_DIR  = Path.home() / ".config" / "pip-companion"
CREDS_FILE  = CONFIG_DIR / "gcal_credentials.json"
TOKEN_FILE  = CONFIG_DIR / "gcal_token.json"

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GCalClient:
    """Thin, thread-safe wrapper around the Google Calendar v3 API."""

    def __init__(self):
        self._service = None
        self._lock    = threading.Lock()

    # ── Status ────────────────────────────────────────────────────────────────

    def is_connected(self) -> bool:
        return TOKEN_FILE.exists()

    def has_credentials_file(self) -> bool:
        return CREDS_FILE.exists()

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _build_service(self) -> bool:
        """Build (or refresh) the service object. Returns True on success."""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            log.error("google-api-python-client not installed")
            return False

        creds = None
        if TOKEN_FILE.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
            except Exception as e:
                log.warning("Could not load token: %s", e)

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            except Exception as e:
                log.warning("Token refresh failed: %s", e)
                creds = None

        if not creds or not creds.valid:
            return False

        with self._lock:
            self._service = build("calendar", "v3", credentials=creds,
                                  cache_discovery=False)
        return True

    def connect(self, on_done=None):
        """
        Start the OAuth flow in a daemon thread.
        on_done(success: bool, message: str) is called when finished.
        """
        def _flow():
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow
            except ImportError:
                msg = "google-auth-oauthlib not installed. Run: pip install google-auth-oauthlib"
                log.error(msg)
                if on_done:
                    on_done(False, msg)
                return

            if not CREDS_FILE.exists():
                msg = (
                    f"Credentials file not found at:\n{CREDS_FILE}\n\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials."
                )
                log.error(msg)
                if on_done:
                    on_done(False, msg)
                return

            try:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
                creds = flow.run_local_server(port=0, open_browser=True)
                TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
                self._build_service()
                log.info("Google Calendar connected successfully")
                if on_done:
                    on_done(True, "Connected!")
            except Exception as exc:
                log.error("GCal connect failed: %s", exc)
                if on_done:
                    on_done(False, str(exc))

        threading.Thread(target=_flow, daemon=True).start()

    def disconnect(self):
        TOKEN_FILE.unlink(missing_ok=True)
        with self._lock:
            self._service = None
        log.info("Google Calendar disconnected")

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_events(self, days: int = 7, max_results: int = 20) -> list[dict]:
        """Return upcoming events within the next `days` days, sorted by start."""
        with self._lock:
            svc = self._service
        if not svc and not self._build_service():
            return []
        with self._lock:
            svc = self._service

        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)
        try:
            result = svc.events().list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=end.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
        except Exception as e:
            log.error("get_events failed: %s", e)
            return []

        events = []
        for e in result.get("items", []):
            start = e.get("start", {})
            dt_str = start.get("dateTime") or start.get("date", "")
            events.append({
                "id":          e.get("id", ""),
                "title":       e.get("summary", "(no title)"),
                "start":       dt_str,
                "location":    e.get("location", ""),
                "description": e.get("description", ""),
                "all_day":     "date" in start and "dateTime" not in start,
            })
        return events

    def get_todays_events(self) -> list[dict]:
        return self.get_events(days=1)

    # ── Write ─────────────────────────────────────────────────────────────────

    def create_event(
        self,
        title: str,
        start_iso: str,
        end_iso: str,
        description: str = "",
        location: str = "",
    ) -> dict | None:
        """
        Create an event on the primary calendar.
        start_iso / end_iso: ISO 8601 datetime strings (e.g. "2026-05-24T14:00:00+05:30").
        Returns the created event dict, or None on failure.
        """
        with self._lock:
            svc = self._service
        if not svc and not self._build_service():
            return None
        with self._lock:
            svc = self._service

        body: dict = {
            "summary": title,
            "start": {"dateTime": start_iso},
            "end":   {"dateTime": end_iso},
        }
        if description:
            body["description"] = description
        if location:
            body["location"] = location

        try:
            event = svc.events().insert(calendarId="primary", body=body).execute()
            log.info("Created event: %s (%s)", title, event.get("id"))
            return event
        except Exception as e:
            log.error("create_event failed: %s", e)
            return None

    def update_event(self, event_id: str, **fields) -> dict | None:
        """
        Update an existing event. Pass keyword args for any top-level event fields
        (e.g. summary="New title"). Returns updated event dict or None.
        """
        with self._lock:
            svc = self._service
        if not svc and not self._build_service():
            return None
        with self._lock:
            svc = self._service

        try:
            event = svc.events().get(calendarId="primary", eventId=event_id).execute()
            for k, v in fields.items():
                event[k] = v
            updated = svc.events().update(
                calendarId="primary", eventId=event_id, body=event
            ).execute()
            log.info("Updated event: %s", event_id)
            return updated
        except Exception as e:
            log.error("update_event failed: %s", e)
            return None

    def delete_event(self, event_id: str) -> bool:
        with self._lock:
            svc = self._service
        if not svc and not self._build_service():
            return False
        with self._lock:
            svc = self._service

        try:
            svc.events().delete(calendarId="primary", eventId=event_id).execute()
            log.info("Deleted event: %s", event_id)
            return True
        except Exception as e:
            log.error("delete_event failed: %s", e)
            return False

    # ── Formatting helpers ────────────────────────────────────────────────────

    @staticmethod
    def format_events_short(events: list[dict], label: str = "Upcoming") -> str:
        """Format events list into a short multi-line string for bubble display."""
        if not events:
            return "No upcoming events found."
        lines = [f"{label} ({len(events)}):"]
        for e in events[:6]:
            title = e["title"][:30] + ("…" if len(e["title"]) > 30 else "")
            if e["all_day"]:
                time_str = e["start"][:10]
            else:
                try:
                    dt = datetime.fromisoformat(e["start"])
                    time_str = dt.strftime("%-d %b %H:%M")
                except Exception:
                    time_str = e["start"][:16]
            lines.append(f"• {time_str} — {title}")
        if len(events) > 6:
            lines.append(f"  …and {len(events) - 6} more")
        return "\n".join(lines)
