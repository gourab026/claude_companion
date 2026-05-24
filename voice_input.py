"""
Voice input — records from microphone and transcribes to text.

Required:  pip install SpeechRecognition pyaudio
Optional (offline mode): pip install openai-whisper
"""

import logging
import os

from PyQt6.QtCore import QThread, pyqtSignal

log = logging.getLogger("pip.voice")

try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except ImportError:
    sr = None
    _SR_AVAILABLE = False

try:
    import whisper as _openai_whisper
    _WHISPER_AVAILABLE = True
except ImportError:
    _openai_whisper = None
    _WHISPER_AVAILABLE = False


class VoiceWorker(QThread):
    """Records audio from the default microphone and emits the transcription."""

    listening_started   = pyqtSignal()    # microphone is open; speak now
    transcription_ready = pyqtSignal(str) # transcription text
    error_occurred      = pyqtSignal(str) # user-facing error message

    def __init__(self, engine: str = "google", language: str = "en-US", parent=None):
        super().__init__(parent)
        self._engine   = engine
        self._language = language

    def run(self):
        if not _SR_AVAILABLE:
            self.error_occurred.emit(
                "SpeechRecognition not installed.\n"
                "Run: pip install SpeechRecognition pyaudio"
            )
            return

        r = sr.Recognizer()
        r.energy_threshold         = 300
        r.dynamic_energy_threshold = True
        r.pause_threshold          = 0.8   # silence before phrase is considered done

        try:
            mic = sr.Microphone()
        except OSError as exc:
            self.error_occurred.emit(f"No microphone found: {exc}")
            return

        try:
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=0.4)
                self.listening_started.emit()
                audio = r.listen(source, timeout=10, phrase_time_limit=30)
        except sr.WaitTimeoutError:
            self.error_occurred.emit("No speech detected — try again.")
            return
        except Exception as exc:
            self.error_occurred.emit(f"Microphone error: {exc}")
            return

        try:
            if self._engine == "whisper":
                text = self._transcribe_whisper(audio)
            else:
                text = r.recognize_google(audio, language=self._language)
        except sr.UnknownValueError:
            self.error_occurred.emit("Couldn't understand — please try again.")
            return
        except sr.RequestError as exc:
            self.error_occurred.emit(f"Speech service error: {exc}")
            return
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            return

        if text and text.strip():
            self.transcription_ready.emit(text.strip())
        else:
            self.error_occurred.emit("Got empty transcription — try again.")

    def _transcribe_whisper(self, audio) -> str:
        if not _WHISPER_AVAILABLE:
            raise RuntimeError(
                "openai-whisper not installed. Run: pip install openai-whisper"
            )
        import tempfile
        import wave

        model = _openai_whisper.load_model("base")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(audio.sample_width)
                wf.setframerate(audio.sample_rate)
                wf.writeframes(audio.get_raw_data())
            result = _openai_whisper.transcribe(model, wav_path,
                                                language=self._language.split("-")[0])
            return result.get("text", "").strip()
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass
