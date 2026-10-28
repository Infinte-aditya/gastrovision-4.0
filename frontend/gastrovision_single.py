"""GastroVision desktop UI (PyQt6).

Contains: splash screen, one-time research-use notice, and the main window.
Talks to the local analysis engine (FastAPI on 127.0.0.1) - nothing leaves the computer.
"""
import os
import sys
import json
import time

import requests
from PyQt6.QtCore import (Qt, QThread, QTimer, pyqtSignal, QUrl, QRectF, QPointF, QPropertyAnimation,
                          QEasingCurve)
from PyQt6.QtGui import (QFont, QFontDatabase, QPixmap, QImage, QPainter, QColor, QPen, QLinearGradient,
                         QDesktopServices, QGuiApplication, QPainterPath)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QFrame, QFileDialog, QGridLayout, QSizePolicy, QScrollArea, QMessageBox, QDialog, QCheckBox,
    QStackedWidget,
)

from app_info import VERSION, FEEDBACK_URL, diagnostics

# ═════════════════════════════════════════════════════════════════════════════
#  THEME
# ═════════════════════════════════════════════════════════════════════════════
BG, SURFACE, BORDER = "#f4f7fa", "#ffffff", "#dbe3ea"
TEXT, MUTED, FAINT = "#0f1f2e", "#5b6b7a", "#8a99a6"
ACCENT, ACCENT_DARK, ACCENT_SOFT = "#0b7285", "#095c6b", "#e3f3f6"
OK, WARN, ERR = "#15803d", "#b45309", "#b91c1c"
VIEWER = "#0e1a23"

QSS = f"""
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#Root, QWidget#ScrollInner {{ background: {BG}; }}
QScrollArea {{ border: none; background: transparent; }}
QLabel {{ color: {TEXT}; background: transparent; }}

QWidget#Header {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QLabel#AppTitle {{ font-size: 18px; font-weight: 700; color: {TEXT}; }}
QLabel#AppSub {{ font-size: 12px; color: {MUTED}; }}

QWidget#Footer {{ background: {SURFACE}; border-top: 1px solid {BORDER}; }}
QLabel#FooterText {{ font-size: 11px; color: {MUTED}; }}

QFrame#Card, QFrame#ResultCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#ResultCard[tone="ok"]      {{ border-left: 5px solid {ACCENT}; }}
QFrame#ResultCard[tone="warn"]    {{ border-left: 5px solid {WARN}; }}
QFrame#ResultCard[tone="neutral"] {{ border-left: 5px solid {FAINT}; }}
QFrame#ResultCard[tone="err"]     {{ border-left: 5px solid {ERR}; }}

QLabel#SectionTitle {{ font-size: 12px; font-weight: 700; color: {MUTED}; }}
QLabel#Caption      {{ font-size: 11px; font-weight: 700; color: {FAINT}; }}
QLabel#Body         {{ font-size: 13px; color: {MUTED}; }}
QLabel#Hint         {{ font-size: 12px; color: {FAINT}; }}
QLabel#BigIcon      {{ font-size: 30px; color: {BORDER}; }}
QLabel#EmptyTitle   {{ font-size: 15px; font-weight: 600; color: {MUTED}; }}
QLabel#ResultTitle  {{ font-size: 27px; font-weight: 700; color: {TEXT}; }}
QLabel#ErrorTitle   {{ font-size: 16px; font-weight: 700; color: {ERR}; }}
QLabel#ErrorText    {{ font-size: 13px; color: {TEXT}; }}
QLabel#ConfVal      {{ font-size: 15px; font-weight: 700; color: {TEXT}; }}
QLabel#KvKey        {{ font-size: 12px; color: {MUTED}; }}
QLabel#KvVal        {{ font-size: 12px; font-weight: 600; color: {TEXT}; }}
QLabel#ElapsedLbl   {{ font-size: 12px; color: {MUTED}; }}
QLabel#PctLbl       {{ font-size: 13px; font-weight: 700; color: {ACCENT_DARK}; }}
QLabel#StepText     {{ font-size: 13px; color: {FAINT}; }}
QLabel#StepText[state="active"] {{ color: {TEXT}; font-weight: 600; }}
QLabel#StepText[state="done"]   {{ color: {MUTED}; }}
QLabel#StepDetail   {{ font-size: 12px; color: {FAINT}; }}

QLabel#Badge {{ font-size: 12px; font-weight: 600; border-radius: 10px; padding: 3px 10px; }}
QLabel#Badge[tone="ok"]      {{ background: {ACCENT_SOFT}; color: {ACCENT_DARK}; }}
QLabel#Badge[tone="warn"]    {{ background: #fdf0dc; color: {WARN}; }}
QLabel#Badge[tone="neutral"] {{ background: #eceff2; color: {MUTED}; }}

QLabel#Pill {{ font-size: 12px; font-weight: 600; border-radius: 12px; padding: 4px 12px; }}
QLabel#Pill[tone="ok"]    {{ background: #e5f5ea; color: {OK}; }}
QLabel#Pill[tone="wait"]  {{ background: #fdf0dc; color: {WARN}; }}
QLabel#Pill[tone="err"]   {{ background: #fbe4e4; color: {ERR}; }}

QLabel#Chip {{ font-size: 12px; color: {MUTED}; background: {BG}; border: 1px solid {BORDER};
               border-radius: 6px; padding: 6px 10px; }}
QLabel#Chip[state="primary"]   {{ background: {ACCENT_SOFT}; border: 1px solid {ACCENT}; color: {ACCENT_DARK}; font-weight: 700; }}
QLabel#Chip[state="secondary"] {{ background: #fdf0dc; border: 1px solid #e9b872; color: {WARN}; font-weight: 600; }}

QFrame#Preview {{ background: {SURFACE}; border: 2px dashed #c3cfd9; border-radius: 10px; }}
QFrame#Preview[hasImage="true"] {{ background: {VIEWER}; border: 1px solid {VIEWER}; }}
QFrame#Preview[dragOver="true"] {{ border: 2px dashed {ACCENT}; background: {ACCENT_SOFT}; }}
QLabel#ViewerCaption {{ font-size: 12px; color: {MUTED}; }}

QPushButton {{ font-size: 13px; }}
QPushButton#Primary {{ background: {ACCENT}; color: white; border: none; border-radius: 8px;
                      font-size: 15px; font-weight: 700; padding: 13px 20px; }}
QPushButton#Primary:hover {{ background: {ACCENT_DARK}; }}
QPushButton#Primary:disabled {{ background: #d5dde4; color: #92a0ac; }}
QPushButton#Secondary {{ background: {SURFACE}; color: {TEXT}; border: 1px solid #c3cfd9; border-radius: 8px;
                        font-weight: 600; padding: 10px 18px; }}
QPushButton#Secondary:hover {{ border-color: {ACCENT}; background: #f1f8fa; }}
QPushButton#Secondary:disabled {{ color: #a9b4be; background: #f4f7fa; border-color: {BORDER}; }}
QPushButton#Ghost {{ background: transparent; color: {ACCENT_DARK}; border: none; border-radius: 8px;
                    font-weight: 600; padding: 10px 14px; }}
QPushButton#Ghost:hover {{ background: {ACCENT_SOFT}; }}
QPushButton#Ghost:disabled {{ color: #b6c0c9; }}
QPushButton#Ghost[danger="true"] {{ color: {ERR}; }}
QPushButton#Ghost[danger="true"]:hover {{ background: #fbe4e4; }}
QPushButton#Nav {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 6px;
                  font-size: 16px; font-weight: 700; padding: 2px 12px; }}
QPushButton#Nav:hover {{ border-color: {ACCENT}; }}

QProgressBar {{ background: #e6ecf1; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QProgressBar#ConfBar {{ max-height: 6px; min-height: 6px; }}

QDialog QCheckBox {{ font-size: 13px; color: {TEXT}; spacing: 8px; }}
"""

PRETTY = {
    "dyed-lifted-polyps": "Dyed lifted polyps",
    "dyed-resection-margins": "Dyed resection margins",
    "esophagitis": "Esophagitis",
    "normal-cecum": "Normal cecum",
    "normal-pylorus": "Normal pylorus",
    "normal-z-line": "Normal Z-line",
    "polyps": "Polyps",
    "ulcerative-colitis": "Ulcerative colitis",
}
LABELS = list(PRETTY)
VIDEO_EXTS = (".mp4", ".avi", ".mkv", ".mov", ".m4v", ".wmv")


def pretty(label: str) -> str:
    if label in PRETTY:
        return PRETTY[label]
    s = (label or "unknown").replace("-", " ").replace("_", " ")
    return s[:1].upper() + s[1:]


def _api() -> str:
    return f"http://127.0.0.1:{os.environ.get('GASTROVISION_PORT', '8000')}"


def _repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def _fmt_time(sec: float) -> str:
    sec = int(max(0, sec))
    return f"{sec // 60}:{sec % 60:02d}"


# ═════════════════════════════════════════════════════════════════════════════
#  SETTINGS (one-time notice)
# ═════════════════════════════════════════════════════════════════════════════
def _settings_path() -> str:
    try:
        import paths
        return os.path.join(paths.data_dir(), "settings.json")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".gastrovision_settings.json")


def load_settings() -> dict:
    try:
        with open(_settings_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(d: dict) -> None:
    try:
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(d, f)
    except Exception:
        pass


def notice_accepted() -> bool:
    return load_settings().get("notice_accepted_version") == VERSION


def remember_notice() -> None:
    s = load_settings()
    s["notice_accepted_version"] = VERSION
    save_settings(s)


# ═════════════════════════════════════════════════════════════════════════════
#  SMALL HELPERS
# ═════════════════════════════════════════════════════════════════════════════
def apply_app_style(app: QApplication) -> None:
    """Pick a clean, readable system font (Segoe UI on Windows) and apply the stylesheet."""
    fams = set(QFontDatabase.families())
    for f in ("Segoe UI", "Inter", "Helvetica Neue", "Arial", "DejaVu Sans"):
        if f in fams:
            app.setFont(QFont(f, 10))
            break
    app.setStyleSheet(QSS)


class Task(QThread):
    """Run a function off the UI thread; emits its result (or the exception object)."""
    done = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn())
        except Exception as e:  # noqa: BLE001
            self.done.emit(e)


class ElidedLabel(QLabel):
    """Single-line label that shortens long text in the middle instead of widening the layout."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(40)
        self._apply()

    def set_full_text(self, t: str):
        self._full = t
        self.setToolTip(t if t and t != "—" else "")
        self._apply()

    def _apply(self):
        w = max(10, self.width() - 2)
        super().setText(self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideMiddle, w))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply()


class LogoMark(QWidget):
    """Endoscope-lens mark, painted so no image file is needed."""

    def __init__(self, size=36, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor("#12a0b8"))
        g.setColorAt(1, QColor("#095c6b"))
        p.setBrush(g)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, r.width() * 0.26, r.width() * 0.26)
        c, s = r.center(), r.width()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("white"), s * 0.07))
        p.drawEllipse(c, s * 0.30, s * 0.30)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 235))
        p.drawEllipse(c, s * 0.15, s * 0.15)
        p.setBrush(QColor("#12a0b8"))
        p.drawEllipse(QPointF(c.x() - s * 0.05, c.y() - s * 0.05), s * 0.045, s * 0.045)


class StepIcon(QWidget):
    """pending = hollow circle, active = spinning arc, done = filled circle with check."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.state = "pending"
        self.angle = 0

    def set_state(self, s: str):
        if s != self.state:
            self.state = s
            self.update()

    def spin(self, a: int):
        self.angle = a
        if self.state == "active":
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(3, 3, 14, 14)
        if self.state == "done":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ACCENT))
            p.drawEllipse(r)
            p.setPen(QPen(QColor("white"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                          Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline([QPointF(6.6, 10.2), QPointF(9, 12.6), QPointF(13.6, 7.4)])
        elif self.state == "active":
            p.setPen(QPen(QColor("#d5e3e8"), 2.2))
            p.drawEllipse(r)
            p.setPen(QPen(QColor(ACCENT), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(r, int(-self.angle * 16), 100 * 16)
        else:
            p.setPen(QPen(QColor("#c3cfd9"), 1.6))
            p.drawEllipse(r)


class ImageView(QLabel):
    """Shows a pixmap scaled to fit, keeping the original so resizing stays sharp."""

    def __init__(self):
        super().__init__()
        self._pm = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setMinimumSize(200, 160)

    def set_full_pixmap(self, pm):
        self._pm = pm
        self._fit()

    def clear_image(self):
        self._pm = None
        self.clear()

    def _fit(self):
        if self._pm is None or self._pm.isNull():
            return
        self.setPixmap(self._pm.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()


# ═════════════════════════════════════════════════════════════════════════════
#  SPLASH SCREEN
# ═════════════════════════════════════════════════════════════════════════════
class SplashScreen(QWidget):
    MIN_MS = 1800   # never flash by faster than this

    def __init__(self):
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(580, 360)
        self._disp, self._floor, self._t0 = 0.0, 0.0, time.time()
        self._finishing, self._cb, self._fading = False, None, False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(52, 44, 52, 44)
        lay.setSpacing(0)
        lay.addWidget(LogoMark(56), alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(18)
        t = QLabel("GastroVision")
        t.setStyleSheet(f"font-size: 30px; font-weight: 700; color: {TEXT};")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        s = QLabel("AI-assisted detection of GI findings in endoscopy video")
        s.setStyleSheet(f"font-size: 13px; color: {MUTED};")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(s)
        lay.addStretch(1)
        self.status = QLabel("Starting…")
        self.status.setStyleSheet(f"font-size: 12px; color: {MUTED};")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(30)                      # the progress track is painted in this gap
        lay.addWidget(self.status)
        lay.addSpacing(16)
        v = QLabel(f"Version {VERSION}  ·  Research prototype")
        v.setStyleSheet(f"font-size: 11px; color: {FAINT};")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(v)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_progress(self, pct: float, text: str = ""):
        self._floor = max(self._floor, float(pct))
        if text:
            self.status.setText(text)

    def finish(self, callback):
        """Fill the bar, fade out, then call callback()."""
        self._finishing, self._cb = True, callback
        self._floor = 100.0
        self.status.setText("Ready")

    def _tick(self):
        cap = 100.0 if self._finishing else 92.0
        self._floor = min(cap, self._floor + (0.035 if not self._finishing else 0))   # slow creep while waiting
        self._disp += (self._floor - self._disp) * 0.07
        if self._disp > self._floor - 0.05:
            self._disp = self._floor
        self.update()
        if self._finishing and not self._fading and self._disp >= 99.5 and \
                (time.time() - self._t0) * 1000 >= self.MIN_MS:
            self._fading = True
            self._anim = QPropertyAnimation(self, b"windowOpacity")
            self._anim.setDuration(260)
            self._anim.setStartValue(1.0)
            self._anim.setEndValue(0.0)
            self._anim.setEasingCurve(QEasingCurve.Type.InQuad)
            self._anim.finished.connect(self._done)
            self._anim.start()

    def _done(self):
        self._timer.stop()
        cb, self._cb = self._cb, None
        if cb:
            cb()
        self.close()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QRectF(self.rect()).adjusted(18, 18, -18, -18)
        for i in range(9, 0, -1):                                  # soft shadow
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(15, 31, 46, 5))
            p.drawRoundedRect(card.adjusted(-i, -i + 4, i, i + 4), 16 + i, 16 + i)
        p.setBrush(QColor(SURFACE))
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawRoundedRect(card, 16, 16)
        # progress track
        x0, x1, y = card.left() + 34, card.right() - 34, card.bottom() - 100
        track = QRectF(x0, y, x1 - x0, 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#e6ecf1"))
        p.drawRoundedRect(track, 3, 3)
        fill = QRectF(x0, y, max(6.0, (x1 - x0) * self._disp / 100.0), 6)
        p.setBrush(QColor(ACCENT))
        p.drawRoundedRect(fill, 3, 3)


# ═════════════════════════════════════════════════════════════════════════════
#  ONE-TIME RESEARCH-USE NOTICE
# ═════════════════════════════════════════════════════════════════════════════
class NoticeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Before you begin")
        self.setModal(True)
        self.setFixedWidth(580)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(0)

        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(LogoMark(40))
        tt = QVBoxLayout()
        tt.setSpacing(0)
        h = QLabel("Before you begin")
        h.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {TEXT};")
        sh = QLabel(f"GastroVision v{VERSION} · Research prototype")
        sh.setStyleSheet(f"font-size: 12px; color: {MUTED};")
        tt.addWidget(h)
        tt.addWidget(sh)
        top.addLayout(tt)
        top.addStretch()
        lay.addLayout(top)
        lay.addSpacing(18)

        body = QLabel(
            "<p style='margin:0 0 10px 0'>GastroVision is a <b>research prototype</b> for exploring "
            "AI-assisted detection of gastrointestinal findings in endoscopy video.</p>"
            "<p style='margin:0 0 6px 0'><b>Not a medical device.</b> It is not cleared or approved by any "
            "regulator. Do not use it to diagnose, treat, or make clinical decisions.</p>"
            "<p style='margin:0 0 6px 0'><b>Results can be wrong.</b> “No finding” is not a clearance. "
            "The model only knows 8 finding types.</p>"
            "<p style='margin:0 0 6px 0'><b>Your videos stay on this computer.</b> Analysis runs locally; "
            "nothing is uploaded.</p>"
            "<p style='margin:0'><b>Protect patient privacy.</b> Never include identifying information "
            "in feedback reports.</p>")
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setStyleSheet(f"font-size: 13px; color: {TEXT}; line-height: 150%;")
        lay.addWidget(body)
        lay.addSpacing(18)

        self.check = QCheckBox("I understand this is a research tool and not for clinical use")
        self.check.toggled.connect(lambda on: self.ok.setEnabled(on))
        lay.addWidget(self.check)
        lay.addSpacing(18)

        row = QHBoxLayout()
        row.addStretch()
        ex = QPushButton("Exit")
        ex.setObjectName("Secondary")
        ex.clicked.connect(self.reject)
        self.ok = QPushButton("Continue")
        self.ok.setObjectName("Primary")
        self.ok.setEnabled(False)
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.accept)
        row.addWidget(ex)
        row.addSpacing(8)
        row.addWidget(self.ok)
        lay.addLayout(row)


# ═════════════════════════════════════════════════════════════════════════════
#  WORKER
# ═════════════════════════════════════════════════════════════════════════════
class AnalysisWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):
        try:
            with open(self.path, "rb") as f:
                files = {"file": (os.path.basename(self.path), f, "application/octet-stream")}
                r = requests.post(f"{_api()}/predict", files=files, timeout=(10, None))
            if r.status_code == 200:
                self.succeeded.emit(r.json())
            else:
                try:
                    detail = r.json().get("detail", r.text)
                except Exception:
                    detail = r.text
                self.failed.emit(f"{r.status_code}|{detail}")
        except requests.exceptions.ConnectionError:
            self.failed.emit("conn|Cannot reach the analysis engine. Please restart GastroVision.")
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"err|{e}")


def probe_video(path: str):
    """Return (QImage thumbnail | None, info dict). Runs in a worker thread."""
    info, img = {}, None
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            n, fps = cap.get(cv2.CAP_PROP_FRAME_COUNT), cap.get(cv2.CAP_PROP_FPS)
            info["w"], info["h"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if fps and fps > 0 and n and n > 0:
                info["duration"] = n / fps
            if n and n > 10:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * 0.1))
            ok, frame = cap.read()
            if ok and frame is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, _ = rgb.shape
                img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        cap.release()
    except Exception:
        pass
    return img, info


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═════════════════════════════════════════════════════════════════════════════
STAGES = [  # key, title
    ("extract", "Reading video"),
    ("filter", "Selecting clear frames"),
    ("predict", "Detecting findings"),
    ("verdict", "Compiling report"),
]
STAGE_RANGE = {"extract": (3, 30), "filter": (30, 40), "predict": (40, 90), "verdict": (90, 99)}

IDLE, LOADED, RUNNING, DONE, FAILED = "idle", "loaded", "running", "done", "failed"


class MainWindow(QMainWindow):
    def __init__(self, health: dict | None = None):
        super().__init__()
        self.setWindowTitle(f"GastroVision {VERSION}")
        self.resize(1200, 820)
        self.setMinimumSize(1000, 760)
        self.setAcceptDrops(True)

        self.health = health or {}
        self.classes = list(self.health.get("classes") or LABELS)
        self.path = None
        self.state = IDLE
        self.worker = None
        self._zombies, self._tasks = [], set()
        self._run_id = 0
        self._thumb = None
        self._frames, self._frame_idx = [], 0
        self._heat, self._heat_idx, self._heat_final = [], 0, False
        self._stage, self._disp_pct, self._floor_pct, self._t0 = "extract", 0.0, 0.0, 0.0
        self._spin, self._prog_busy, self._health_busy = 0, False, False
        self._n_frames = 0

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._build_header())
        rl.addWidget(self._build_body(), 1)
        rl.addWidget(self._build_footer())

        self._tick_t = QTimer(self, interval=60, timeout=self._tick)
        self._prog_t = QTimer(self, interval=700, timeout=self._poll_progress)
        self._frames_t = QTimer(self, interval=900, timeout=self._cycle_frames)
        self._heat_poll_t = QTimer(self, interval=1500, timeout=self._poll_heatmaps)
        self._auto_t = QTimer(self, interval=2800, timeout=lambda: self._heat_step(1, manual=False))
        self._health_t = QTimer(self, interval=5000, timeout=self._poll_health)
        self._health_t.start()
        self._show_image(None, "")
        self._set_state(IDLE)

    # ───────────────────────── layout ─────────────────────────
    def _build_header(self):
        h = QWidget()
        h.setObjectName("Header")
        h.setFixedHeight(68)
        hl = QHBoxLayout(h)
        hl.setContentsMargins(24, 0, 24, 0)
        hl.setSpacing(14)
        hl.addWidget(LogoMark(38))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addStretch()
        t = QLabel("GastroVision")
        t.setObjectName("AppTitle")
        s = QLabel(f"GI finding detection  ·  v{VERSION}  ·  Research prototype")
        s.setObjectName("AppSub")
        col.addWidget(t)
        col.addWidget(s)
        col.addStretch()
        hl.addLayout(col)
        hl.addStretch()
        fb = QPushButton("Send feedback")
        fb.setObjectName("Secondary")
        fb.setCursor(Qt.CursorShape.PointingHandCursor)
        fb.clicked.connect(self._send_feedback)
        hl.addWidget(fb)
        self.pill = QLabel("Engine ready")
        self.pill.setObjectName("Pill")
        self.pill.setProperty("tone", "ok")
        self.pill.setFixedHeight(26)
        hl.addWidget(self.pill, alignment=Qt.AlignmentFlag.AlignVCenter)
        return h

    def _section(self, text):
        l = QLabel(text.upper())
        l.setObjectName("SectionTitle")
        return l

    def _build_body(self):
        body = QWidget()
        body.setObjectName("Root")
        bl = QHBoxLayout(body)
        bl.setContentsMargins(24, 20, 24, 20)
        bl.setSpacing(22)
        bl.addLayout(self._build_left(), 3)

        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("ScrollInner")
        inner.setLayout(self._build_right())
        sc.setWidget(inner)
        sc.setMinimumWidth(400)
        bl.addWidget(sc, 2)
        return body

    # left: viewer + steps
    def _build_left(self):
        L = QVBoxLayout()
        L.setSpacing(10)
        L.addWidget(self._section("Video"))

        self.preview = QFrame()
        self.preview.setObjectName("Preview")
        self.preview.setProperty("hasImage", False)
        self.preview.setMinimumHeight(200)
        pl = QVBoxLayout(self.preview)
        pl.setContentsMargins(8, 8, 8, 8)
        self.stack = QStackedWidget()
        # page 0: empty drop zone
        e = QWidget()
        el = QVBoxLayout(e)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic = QLabel("▶")
        ic.setObjectName("BigIcon")
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        et = QLabel("Drop an endoscopy video here")
        et.setObjectName("EmptyTitle")
        et.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eh = QLabel("or choose a file with “Select video”  ·  MP4, AVI, MKV, MOV")
        eh.setObjectName("Hint")
        eh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (ic, et, eh):
            el.addWidget(w)
        self.stack.addWidget(e)
        # page 1: image
        self.view = ImageView()
        self.stack.addWidget(self.view)
        pl.addWidget(self.stack)
        L.addWidget(self.preview, 1)

        # viewer caption + heatmap navigation
        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.prev_btn = QPushButton("‹")
        self.prev_btn.setObjectName("Nav")
        self.next_btn = QPushButton("›")
        self.next_btn.setObjectName("Nav")
        self.prev_btn.clicked.connect(lambda: self._heat_step(-1, manual=True))
        self.next_btn.clicked.connect(lambda: self._heat_step(1, manual=True))
        self.caption = QLabel("")
        self.caption.setObjectName("ViewerCaption")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.caption, 1)
        nav.addWidget(self.next_btn)
        self.nav_w = QWidget()
        self.nav_w.setLayout(nav)
        nav.setContentsMargins(0, 2, 0, 0)
        self.nav_w.setFixedHeight(30)
        L.addWidget(self.nav_w)

        # buttons
        row = QHBoxLayout()
        row.setSpacing(8)
        self.select_btn = QPushButton("Select video")
        self.select_btn.setObjectName("Secondary")
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.clicked.connect(self.pick_video)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("Ghost")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_or_cancel)
        row.addWidget(self.select_btn)
        row.addWidget(self.clear_btn)
        row.addStretch()
        L.addLayout(row)

        # analysis panel
        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 14, 18, 16)
        cl.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(self._section("Analysis"))
        head.addStretch()
        self.elapsed = QLabel("")
        self.elapsed.setObjectName("ElapsedLbl")
        head.addWidget(self.elapsed)
        cl.addLayout(head)

        self.steps = []
        for key, title in STAGES:
            r = QHBoxLayout()
            r.setSpacing(10)
            icon = StepIcon()
            txt = QLabel(title)
            txt.setObjectName("StepText")
            txt.setProperty("state", "pending")
            det = QLabel("")
            det.setObjectName("StepDetail")
            r.addWidget(icon)
            r.addWidget(txt)
            r.addStretch()
            r.addWidget(det)
            cl.addLayout(r)
            self.steps.append((key, icon, txt, det))

        pr = QHBoxLayout()
        pr.setSpacing(12)
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 1000)
        self.pbar.setTextVisible(False)
        self.pct = QLabel("0%")
        self.pct.setObjectName("PctLbl")
        self.pct.setFixedWidth(44)
        self.pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pr.addWidget(self.pbar, 1)
        pr.addWidget(self.pct)
        cl.addSpacing(4)
        cl.addLayout(pr)

        self.status = QLabel("")
        self.status.setObjectName("Body")
        self.status.setWordWrap(True)
        cl.addWidget(self.status)
        L.addWidget(card)

        self.run_btn = QPushButton("Analyse video")
        self.run_btn.setObjectName("Primary")
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.clicked.connect(self.run_analysis)
        L.addWidget(self.run_btn)
        return L

    # right: result + file + classes
    def _build_right(self):
        R = QVBoxLayout()
        R.setContentsMargins(0, 0, 4, 0)
        R.setSpacing(10)
        R.addWidget(self._section("Result"))

        self.result_card = QFrame()
        self.result_card.setObjectName("ResultCard")
        self.result_card.setProperty("tone", "neutral")
        rc = QVBoxLayout(self.result_card)
        rc.setContentsMargins(22, 18, 22, 18)
        self.rstack = QStackedWidget()
        rc.addWidget(self.rstack)

        # 0 empty
        p0 = QWidget()
        l0 = QVBoxLayout(p0)
        l0.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l0.setSpacing(4)
        for txt, obj in (("◎", "BigIcon"), ("No analysis yet", "EmptyTitle"),
                         ("Select a video, then press “Analyse video”.", "Hint")):
            lb = QLabel(txt)
            lb.setObjectName(obj)
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb.setWordWrap(True)
            l0.addWidget(lb)
        self.rstack.addWidget(p0)

        # 1 running
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l1.setSpacing(4)
        self.run_title = QLabel("Analysing video…")
        self.run_title.setObjectName("EmptyTitle")
        self.run_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.run_sub = QLabel("This can take a few minutes for long recordings.")
        self.run_sub.setObjectName("Hint")
        self.run_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.run_sub.setWordWrap(True)
        l1.addWidget(self.run_title)
        l1.addWidget(self.run_sub)
        self.rstack.addWidget(p1)

        # 2 result
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        l2.setContentsMargins(0, 0, 0, 0)
        l2.setSpacing(6)
        cap = QLabel("PRIMARY FINDING")
        cap.setObjectName("Caption")
        self.res_title = QLabel("")
        self.res_title.setObjectName("ResultTitle")
        self.res_title.setWordWrap(True)
        self.res_badge = QLabel("")
        self.res_badge.setObjectName("Badge")
        self.res_badge.setProperty("tone", "ok")
        brow = QHBoxLayout()
        brow.addWidget(self.res_badge)
        brow.addStretch()
        l2.addWidget(cap)
        l2.addWidget(self.res_title)
        l2.addLayout(brow)
        l2.addSpacing(6)
        self.conf_w = QWidget()
        cw = QVBoxLayout(self.conf_w)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.setSpacing(4)
        cr = QHBoxLayout()
        ck = QLabel("Mean confidence")
        ck.setObjectName("KvKey")
        self.conf_val = QLabel("")
        self.conf_val.setObjectName("ConfVal")
        cr.addWidget(ck)
        cr.addStretch()
        cr.addWidget(self.conf_val)
        self.conf_bar = QProgressBar()
        self.conf_bar.setObjectName("ConfBar")
        self.conf_bar.setRange(0, 1000)
        self.conf_bar.setTextVisible(False)
        cw.addLayout(cr)
        cw.addWidget(self.conf_bar)
        l2.addWidget(self.conf_w)
        self.res_note = QLabel("")
        self.res_note.setObjectName("Body")
        self.res_note.setWordWrap(True)
        l2.addWidget(self.res_note)
        self.also_title = QLabel("ALSO SEEN")
        self.also_title.setObjectName("Caption")
        self.also = QLabel("")
        self.also.setObjectName("Body")
        self.also.setWordWrap(True)
        self.also.setTextFormat(Qt.TextFormat.RichText)
        l2.addSpacing(4)
        l2.addWidget(self.also_title)
        l2.addWidget(self.also)
        self.rstack.addWidget(p2)

        # 3 error
        p3 = QWidget()
        l3 = QVBoxLayout(p3)
        l3.setSpacing(6)
        et = QLabel("Analysis could not be completed")
        et.setObjectName("ErrorTitle")
        et.setWordWrap(True)
        self.err_text = QLabel("")
        self.err_text.setObjectName("ErrorText")
        self.err_text.setWordWrap(True)
        self.err_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        eh = QLabel("You can try again, or use “Send feedback” if this keeps happening.")
        eh.setObjectName("Hint")
        eh.setWordWrap(True)
        for w in (et, self.err_text, eh):
            l3.addWidget(w)
        self.rstack.addWidget(p3)
        R.addWidget(self.result_card)

        # file details
        R.addSpacing(4)
        R.addWidget(self._section("File"))
        fc = QFrame()
        fc.setObjectName("Card")
        g = QGridLayout(fc)
        g.setContentsMargins(18, 14, 18, 14)
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(8)
        g.setColumnStretch(1, 1)
        self.kv = {}
        for i, k in enumerate(("Name", "Format", "Size", "Duration", "Resolution", "Folder")):
            kl = QLabel(k)
            kl.setObjectName("KvKey")
            vl = ElidedLabel("—")
            vl.setObjectName("KvVal")
            g.addWidget(kl, i, 0)
            g.addWidget(vl, i, 1)
            self.kv[k] = vl
        R.addWidget(fc)

        # classes
        R.addSpacing(4)
        R.addWidget(self._section(f"Findings the model recognises ({len(self.classes)})"))
        cc = QFrame()
        cc.setObjectName("Card")
        cg = QGridLayout(cc)
        cg.setContentsMargins(14, 14, 14, 14)
        cg.setSpacing(8)
        self.chips = {}
        for i, c in enumerate(self.classes):
            chip = QLabel(pretty(c))
            chip.setObjectName("Chip")
            chip.setProperty("state", "idle")
            cg.addWidget(chip, i // 2, i % 2)
            self.chips[c] = chip
        R.addWidget(cc)
        R.addStretch(1)
        return R

    def _build_footer(self):
        f = QWidget()
        f.setObjectName("Footer")
        f.setFixedHeight(34)
        fl = QHBoxLayout(f)
        fl.setContentsMargins(24, 0, 24, 0)
        prov = str(self.health.get("provider", ""))
        hw = "GPU (DirectML)" if "Dml" in prov else ("CPU" if prov else "")
        left = "Research prototype · not a medical device · videos are processed on this computer only"
        self.hw_lbl = QLabel(f"Running on {hw}" if hw else "")
        self.hw_lbl.setObjectName("FooterText")
        l = QLabel(left)
        l.setObjectName("FooterText")
        fl.addWidget(l)
        fl.addStretch()
        fl.addWidget(self.hw_lbl)
        return f

    # ───────────────────────── state machine ─────────────────────────
    def _set_state(self, st: str):
        self.state = st
        running = st == RUNNING
        has = self.path is not None
        self.run_btn.setEnabled(has and not running)
        self.run_btn.setText("Analysing…" if running else ("Analyse again" if st in (DONE, FAILED) else "Analyse video"))
        self.select_btn.setEnabled(not running)
        self.select_btn.setText("Change video" if has else "Select video")
        self.clear_btn.setEnabled(has or running)
        self.clear_btn.setText("Cancel" if running else "Clear")
        self.clear_btn.setProperty("danger", running)
        _repolish(self.clear_btn)
        steps_visible = running or st in (DONE,)
        for _, icon, txt, det in self.steps:
            if not steps_visible:
                icon.set_state("pending")
                self._step_text(txt, "pending")
                det.setText("")
        if st in (IDLE, LOADED, FAILED):
            self.pbar.setValue(0)
            self.pct.setText("")
            self.elapsed.setText("")
        self.rstack.setCurrentIndex({IDLE: 0, LOADED: 0, RUNNING: 1, DONE: 2, FAILED: 3}[st])
        if st in (IDLE, LOADED):
            self._set_tone("neutral")
        self.status.setText({
            IDLE: "Select a video to begin.",
            LOADED: "Video loaded. Ready to analyse.",
            RUNNING: "",
            DONE: "Analysis complete.",
            FAILED: "Analysis failed.",
        }[st])

    def _set_tone(self, tone: str):
        self.result_card.setProperty("tone", tone)
        _repolish(self.result_card)

    @staticmethod
    def _step_text(lbl: QLabel, state: str):
        lbl.setProperty("state", state)
        _repolish(lbl)

    # ───────────────────────── video selection ─────────────────────────
    def pick_video(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Select endoscopy video", "",
            "Video files (*.mp4 *.avi *.mkv *.mov *.m4v *.wmv);;All files (*)")
        if p:
            self.load_video(p)

    def load_video(self, p: str):
        self._stop_timers()
        self._heat, self._frames = [], []
        self.path = p
        self._reset_chips()
        name = os.path.basename(p)
        size_mb = os.path.getsize(p) / (1024 * 1024)
        self.kv["Name"].set_full_text(name)
        self.kv["Format"].set_full_text(os.path.splitext(name)[1].upper().lstrip("."))
        self.kv["Size"].set_full_text(f"{size_mb:.1f} MB")
        self.kv["Duration"].set_full_text("…")
        self.kv["Resolution"].set_full_text("…")
        self.kv["Folder"].set_full_text(os.path.dirname(p))
        self._show_image(None, "")
        self._set_state(LOADED)
        t = Task(lambda: probe_video(p))
        t.done.connect(lambda r, path=p: self._on_probe(r, path))
        self._run_task(t)

    def _on_probe(self, r, path):
        if path != self.path:
            return
        img, info = (r if isinstance(r, tuple) else (None, {}))
        self.kv["Duration"].set_full_text(_fmt_time(info["duration"]) if "duration" in info else "—")
        self.kv["Resolution"].set_full_text(f"{info['w']} × {info['h']}" if info.get("w") else "—")
        if img is not None and self.state in (LOADED, FAILED):
            self._thumb = QPixmap.fromImage(img)
            self._show_image(self._thumb, "Preview (frame from the video)")

    def _show_image(self, pm, caption: str, nav=False):
        has = pm is not None
        if has:
            self.view.set_full_pixmap(pm)
        else:
            self.view.clear_image()
        self.stack.setCurrentIndex(1 if has else 0)
        self.preview.setProperty("hasImage", has)
        _repolish(self.preview)
        self.caption.setText(caption)
        self.prev_btn.setVisible(nav)
        self.next_btn.setVisible(nav)
        self.nav_w.setVisible(has and bool(caption))

    # drag & drop
    def dragEnterEvent(self, e):
        if self.state != RUNNING and e.mimeData().hasUrls() and any(
                u.toLocalFile().lower().endswith(VIDEO_EXTS) for u in e.mimeData().urls()):
            e.acceptProposedAction()
            self.preview.setProperty("dragOver", True)
            _repolish(self.preview)

    def dragLeaveEvent(self, e):
        self.preview.setProperty("dragOver", False)
        _repolish(self.preview)

    def dropEvent(self, e):
        self.dragLeaveEvent(e)
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p.lower().endswith(VIDEO_EXTS):
                self.load_video(p)
                break

    # ───────────────────────── run / cancel ─────────────────────────
    def run_analysis(self):
        if not self.path or self.state == RUNNING:
            return
        self._stop_timers()
        self._run_id += 1
        rid = self._run_id
        self._heat, self._frames, self._heat_final = [], [], False
        self._reset_chips()
        self._stage, self._disp_pct, self._floor_pct, self._n_frames = "extract", 0.0, 3.0, 0
        self._t0 = time.time()
        self._set_state(RUNNING)
        self._set_tone("neutral")
        self._apply_stage("extract", 0)
        self.status.setText("Preparing the video…")
        if self._thumb is not None:
            self._show_image(self._thumb, "Analysing…")
        self.worker = AnalysisWorker(self.path)
        self.worker.succeeded.connect(lambda r, i=rid: self._on_success(r, i))
        self.worker.failed.connect(lambda m, i=rid: self._on_error(m, i))
        self.worker.finished.connect(self._reap_workers)
        self.worker.start()
        self._tick_t.start()
        self._prog_t.start()
        self._frames_t.start()

    def _clear_or_cancel(self):
        if self.state == RUNNING:
            name = os.path.splitext(os.path.basename(self.path))[0]
            self._run_id += 1                                   # ignore the late result
            self._zombies.append(self.worker)                   # let the HTTP call finish in the background
            self.worker = None
            self._stop_timers()
            t = Task(lambda: requests.post(f"{_api()}/cancel/{name}", timeout=3))
            self._run_task(t)
            self._set_state(LOADED)
            self._show_image(self._thumb, "Preview (frame from the video)") if self._thumb else self._show_image(None, "")
            self.status.setText("Analysis cancelled. The engine stops after its current step.")
            return
        self._stop_timers()
        self.path, self._thumb, self._heat, self._frames = None, None, [], []
        for v in self.kv.values():
            v.set_full_text("—")
        self._reset_chips()
        self._show_image(None, "")
        self._set_state(IDLE)

    def _reap_workers(self):
        self._zombies = [z for z in self._zombies if z.isRunning()]

    # ───────────────────────── progress ─────────────────────────
    def _apply_stage(self, stage: str, n_frames: int):
        if stage not in STAGE_RANGE:
            return
        self._stage = stage
        self._floor_pct = max(self._floor_pct, STAGE_RANGE[stage][0])
        idx = [k for k, *_ in STAGES].index(stage)
        for i, (key, icon, txt, det) in enumerate(self.steps):
            if i < idx:
                icon.set_state("done")
                self._step_text(txt, "done")
                det.setText("")
            elif i == idx:
                icon.set_state("active")
                self._step_text(txt, "active")
            else:
                icon.set_state("pending")
                self._step_text(txt, "pending")
                det.setText("")
        if n_frames:
            self._n_frames = n_frames
            self.steps[2][3].setText(f"{n_frames} frames")
        msgs = {"extract": "Extracting frames from the video…", "filter": "Discarding blurry or unusable frames…",
                "predict": "Looking for findings in each frame…", "verdict": "Combining frame results into a verdict…"}
        self.status.setText(msgs[stage])

    def _tick(self):
        self._spin = (self._spin + 14) % 360
        for _, icon, *_ in self.steps:
            icon.spin(self._spin)
        lo, hi = STAGE_RANGE.get(self._stage, (3, 99))
        if self._disp_pct < self._floor_pct:
            self._disp_pct += max(0.4, (self._floor_pct - self._disp_pct) * 0.25)
        else:
            self._disp_pct += max(0.0, (hi - 1 - self._disp_pct)) * 0.006
        self._disp_pct = min(self._disp_pct, 99.0)
        self.pbar.setValue(int(self._disp_pct * 10))
        self.pct.setText(f"{int(self._disp_pct)}%")
        self.elapsed.setText(f"Elapsed {_fmt_time(time.time() - self._t0)}")

    def _poll_progress(self):
        if self._prog_busy or not self.path or self.state != RUNNING:
            return
        name = os.path.splitext(os.path.basename(self.path))[0]
        rid = self._run_id
        self._prog_busy = True
        t = Task(lambda: requests.get(f"{_api()}/progress/{name}", timeout=2).json())
        t.done.connect(lambda r, i=rid: self._on_progress(r, i))
        self._run_task(t)

    def _on_progress(self, r, rid):
        self._prog_busy = False
        if rid != self._run_id or self.state != RUNNING or not isinstance(r, dict):
            return
        st = r.get("stage")
        if st in STAGE_RANGE and (st != self._stage or r.get("n_frames", 0) != self._n_frames):
            self._apply_stage(st, int(r.get("n_frames", 0) or 0))

    def _cycle_frames(self):
        """While the model runs, flip through the frames it is looking at."""
        if self.state != RUNNING or not self.path:
            return
        try:
            import paths
            base = os.path.join(paths.outputs_dir(), os.path.splitext(os.path.basename(self.path))[0])
        except Exception:
            return
        for sub in ("cleaned_frames", "frames"):
            d = os.path.join(base, sub)
            if os.path.isdir(d):
                try:
                    fs = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
                except OSError:
                    fs = []
                if fs and self._stage in ("predict", "verdict", "filter"):
                    self._frame_idx = (self._frame_idx + max(1, len(fs) // 24)) % len(fs)
                    pm = QPixmap(os.path.join(d, fs[self._frame_idx]))
                    if not pm.isNull():
                        self._show_image(pm, f"Analysing frames…  ({len(fs)} selected)")
                    return

    # ───────────────────────── results ─────────────────────────
    def _on_success(self, result: dict, rid: int):
        if rid != self._run_id:
            return
        self._stop_timers()
        self._set_state(DONE)
        for icon_i, (_, icon, txt, det) in enumerate(self.steps):
            icon.set_state("done")
            self._step_text(txt, "done")
        self.steps[2][3].setText(f"{result.get('n_frames', self._n_frames)} frames" if result.get("n_frames") else "")
        self.pbar.setValue(1000)
        self.pct.setText("100%")
        self.elapsed.setText(f"Finished in {_fmt_time(time.time() - self._t0)}")
        self.status.setText("Analysis complete. Generating heatmaps…")

        label = result.get("label", "unknown")
        conf = float(result.get("confidence", 0.0) or 0.0)
        findings = result.get("findings", []) or []
        if label == "no-finding":
            self._set_tone("neutral")
            self.res_title.setText("No consistent finding")
            self._badge("Not a clearance", "neutral")
            self.conf_w.hide()
            unc = float(result.get("uncertain_fraction", 1.0) or 0.0)
            self.res_note.setText(f"{unc * 100:.0f}% of frames were uncertain or outside the model’s 8 known "
                                  "findings. This is not a clearance: the model cannot rule out anything "
                                  "it was not trained on.")
            self.also_title.hide()
            self.also.hide()
        else:
            possible = bool(findings) and findings[0].get("strength") == "possible"
            self._set_tone("warn" if possible else "ok")
            self.res_title.setText(pretty(label))
            self._badge("Possible finding · please review" if possible else "Finding detected",
                        "warn" if possible else "ok")
            self.conf_w.show()
            self.conf_val.setText(f"{conf * 100:.1f}%")
            self.conf_bar.setValue(int(max(0.0, min(1.0, conf)) * 1000))
            self.res_note.setText("Below the standard confidence bar. Please review the highlighted frames."
                                  if possible else "")
            self.res_note.setVisible(possible)
            others = findings[1:]
            if others:
                rows = []
                for f in others:
                    s = pretty(f.get("class", "?"))
                    if f.get("strength") == "possible":
                        s += " <span style='color:%s'>(possible)</span>" % WARN
                    rows.append(s)
                self.also.setText("<br>".join(rows))
                self.also_title.show()
                self.also.show()
            else:
                self.also_title.hide()
                self.also.hide()
        self.res_note.setVisible(bool(self.res_note.text()))

        names = {f.get("class") for f in findings}
        for c, chip in self.chips.items():
            chip.setProperty("state", "primary" if c == label else ("secondary" if c in names else "idle"))
            _repolish(chip)

        self._heat_final = False
        self._heat_poll_t.start()
        self._poll_heatmaps()

    def _badge(self, text, tone):
        self.res_badge.setText(text)
        self.res_badge.setProperty("tone", tone)
        _repolish(self.res_badge)

    def _on_error(self, msg: str, rid: int):
        if rid != self._run_id:
            return
        self._stop_timers()
        kind, _, detail = msg.partition("|")
        if kind == "499":
            self._set_state(LOADED)
            return
        self._set_state(FAILED)
        self._set_tone("err")
        self.err_text.setText(detail or msg)
        self.status.setText("Analysis failed.")
        if self._thumb is not None:
            self._show_image(self._thumb, "Preview (frame from the video)")

    # heatmaps
    def _poll_heatmaps(self):
        if self.state != DONE or not self.path:
            self._heat_poll_t.stop()
            return
        name = os.path.splitext(os.path.basename(self.path))[0]
        rid = self._run_id
        t = Task(lambda: requests.get(f"{_api()}/heatmaps/{name}", timeout=3).json())
        t.done.connect(lambda r, i=rid: self._on_heatmaps(r, i))
        self._run_task(t)

    def _on_heatmaps(self, body, rid):
        if rid != self._run_id or self.state != DONE or not isinstance(body, dict):
            return
        paths_ = [p for p in body.get("heatmap_paths", []) if os.path.exists(p)]
        done = bool(body.get("done")) or len(paths_) >= 5
        if paths_ and paths_ != self._heat:
            first = not self._heat
            self._heat = paths_
            if first:
                self._heat_idx = 0
                self._show_heat()
                self._auto_t.start()
        if done:
            self._heat_poll_t.stop()
            if paths_:
                self.status.setText("Analysis complete. Heatmaps show where the model looked.")
            else:
                self.status.setText("Analysis complete. No heatmaps (no finding to highlight).")
                if self._thumb is not None:
                    self._show_image(self._thumb, "No heatmaps: no finding to highlight")

    def _show_heat(self):
        if not self._heat:
            return
        pm = QPixmap(self._heat[self._heat_idx % len(self._heat)])
        if not pm.isNull():
            self._show_image(pm, f"Heatmap {self._heat_idx % len(self._heat) + 1} of {len(self._heat)}  ·  "
                                 "where the model looked", nav=len(self._heat) > 1)

    def _heat_step(self, d: int, manual: bool):
        if not self._heat or self.state != DONE:
            return
        if manual:
            self._auto_t.stop()
        self._heat_idx = (self._heat_idx + d) % len(self._heat)
        self._show_heat()

    # ───────────────────────── misc ─────────────────────────
    def _reset_chips(self):
        for chip in self.chips.values():
            chip.setProperty("state", "idle")
            _repolish(chip)

    def _stop_timers(self):
        for t in (self._tick_t, self._prog_t, self._frames_t, self._heat_poll_t, self._auto_t):
            t.stop()
        self._prog_busy = False

    def _run_task(self, t: Task):
        self._tasks.add(t)
        t.finished.connect(lambda t=t: self._tasks.discard(t))
        t.start()

    def _poll_health(self):
        if self._health_busy:
            return
        self._health_busy = True
        t = Task(lambda: requests.get(f"{_api()}/health", timeout=3).json())
        t.done.connect(self._on_health)
        self._run_task(t)

    def _on_health(self, r):
        self._health_busy = False
        ok = isinstance(r, dict) and r.get("status") == "ok"
        busy = self.state == RUNNING and not isinstance(r, dict)   # engine busy loading? keep calm during runs
        if ok:
            tone, text = "ok", "Engine ready"
        elif busy:
            tone, text = "wait", "Engine busy"
        else:
            tone, text = "err", "Engine offline"
        self.pill.setText(text)
        self.pill.setProperty("tone", tone)
        _repolish(self.pill)

    def _send_feedback(self):
        QGuiApplication.clipboard().setText(diagnostics())
        QMessageBox.information(
            self, "Send feedback",
            "Your browser will open the feedback form.\n\n"
            "A few technical details (app version, operating system) were copied to your clipboard. "
            "Please paste them into the form.\n\n"
            "Do NOT upload or describe patient-identifying information.")
        QDesktopServices.openUrl(QUrl(FEEDBACK_URL))

    def closeEvent(self, e):
        if self.state == RUNNING:
            if QMessageBox.question(self, "Analysis in progress",
                                    "An analysis is still running. Quit anyway?") != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
        self._stop_timers()
        e.accept()


# ═════════════════════════════════════════════════════════════════════════════
#  STANDALONE (development) ENTRY POINT - the installed app starts via launcher.py
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_app_style(app)
    if not notice_accepted():
        d = NoticeDialog()
        if d.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        remember_notice()
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
