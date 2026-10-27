import sys
import os
import requests
from app_info import VERSION, FEEDBACK_URL, diagnostics

API = f"http://127.0.0.1:{os.environ.get('GASTROVISION_PORT', '8000')}"
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QFrame, QFileDialog, QGridLayout,
    QSizePolicy, QScrollArea, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPixmap, QColor, QPalette, QFontDatabase, QDesktopServices, QGuiApplication
from PyQt6.QtCore import QUrl

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer

# ─────────────────────────────────────────────
#  STYLESHEET
# ─────────────────────────────────────────────
QSS = """
QMainWindow, QWidget#Root {
    background-color: #f0f2f5;
}

/* ── Header ── */
QWidget#Header {
    background-color: #ffffff;
    border-bottom: 1px solid #d1d5db;
    min-height: 52px;
    max-height: 52px;
}
QLabel#AppTitle {
    color: #1a1d2e;
    font-family: "Courier New";
    font-size: 16px;
    font-weight: bold;
    letter-spacing: 4px;
    padding-left: 24px;
}
QLabel#AppSubtitle {
    color: #4b53bc;
    font-family: "Courier New";
    font-size: 10px;
    letter-spacing: 2px;
    padding-left: 24px;
}
QLabel#StatusDot {
    color: #22c55e;
    font-size: 10px;
    padding-right: 12px;
}

/* ── Footer ── */
QWidget#Footer {
    background-color: #4b53bc;
    min-height: 24px;
    max-height: 24px;
}
QLabel#FooterLabel {
    color: #ffffff;
    font-family: "Courier New";
    font-size: 10px;
    padding: 0 12px;
}

/* ── Cards / Frames ── */
QFrame#Card {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 6px;
}
QFrame#ResultCard {
    background-color: #0d1a0f;
    border: 1px solid #166534;
    border-radius: 6px;
}
QFrame#ErrorCard {
    background-color: #1a0d0d;
    border: 1px solid #7f1d1d;
    border-radius: 6px;
}
QFrame#ImageBox {
    background-color: #f8f9fa;
    border: 2px dashed #c0c4cc;
    border-radius: 6px;
    min-height: 340px;
}
QFrame#ImageBox[hasImage=true] {
    border: 2px solid #4b53bc;
}

/* ── Labels ── */
QLabel#SectionTitle {
    color: #4b53bc;
    font-family: "Courier New";
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 3px;
}
QLabel#BodyLabel {
    color: #4b5563;
    font-family: "Courier New";
    font-size: 11px;
}
QLabel#PlaceholderLabel {
    color: #2a2f3e;
    font-family: "Courier New";
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 2px;
}
QLabel#ResultLabel {
    color: #22c55e;
    font-family: "Courier New";
    font-size: 28px;
    font-weight: bold;
    letter-spacing: 3px;
}
QLabel#ResultSubLabel {
    color: #4ade80;
    font-family: "Courier New";
    font-size: 11px;
    letter-spacing: 2px;
}
QLabel#ErrorLabel {
    color: #f87171;
    font-family: "Courier New";
    font-size: 13px;
    letter-spacing: 1px;
}
QLabel#PropKey {
    color: #4b53bc;
    font-family: "Courier New";
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
}
QLabel#PropVal {
    color: #1a1d2e;
    font-family: "Courier New";
    font-size: 11px;
    font-weight: bold;
    background-color: #e0e7ff;
    padding: 4px 8px;
    border-radius: 3px;
    
}

/* ── Buttons ── */
QPushButton#UploadBtn {
    background-color: #f0f2f5;
    color: #1a1d2e;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-family: "Courier New";
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 2px;
    padding: 10px 24px;
}
QPushButton#UploadBtn:hover {
    background-color: #252b3d;
    border-color: #4b53bc;
    color: #ffffff;
}
QPushButton#UploadBtn:pressed {
    background-color: #4b53bc;
}

QPushButton#ExecuteBtn {
    background-color: #4b53bc;
    color: #ffffff;
    border: 1px solid #3a42a0;
    border-radius: 4px;
    font-family: "Courier New";
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 3px;
    padding: 14px;
    min-height: 48px;
}
QPushButton#ExecuteBtn:hover {
    background-color: #5c65d4;
}
QPushButton#ExecuteBtn:pressed {
    background-color: #3a42a0;
}
QPushButton#ExecuteBtn:disabled {
    background-color: #e5e7eb;
    color: #9ca3af;
}

QPushButton#ClearBtn {
    background-color: transparent;
    color: #4b53bc;
    border: 1px solid #2a2f3e;
    border-radius: 4px;
    font-family: "Courier New";
    font-size: 11px;
    letter-spacing: 2px;
    padding: 6px 16px;
}
QPushButton#ClearBtn:hover {
    background-color: #1e2230;
    border-color: #4b53bc;
}

/* ── Progress Bar ── */
QProgressBar {
    background-color: #e5e7eb;
    border: 1px solid #d1d5db;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #4b53bc;
    border-radius: 3px;
}
QProgressBar[busy=true]::chunk {
    background-color: #22c55e;
}

/* ── Class labels (diagnoses) ── */
QLabel#ClassChip {
    background-color: #f0f2f5;
    color: #4b53bc;
    border: 1px solid #d1d5db;
    border-radius: 3px;
    font-family: "Courier New";
    font-size: 10px;
    letter-spacing: 1px;
    padding: 4px 10px;
}
QLabel#ClassChipActive {
    background-color: #dcfce7;
    color: #166534;
    border: 1px solid #86efac;
    border-radius: 3px;
    font-family: "Courier New";
    font-size: 10px;
    letter-spacing: 1px;
    padding: 4px 10px;
    font-weight: bold;
}
"""

# ─────────────────────────────────────────────
#  WORKER THREAD
# ─────────────────────────────────────────────
class AnalysisWorker(QThread):
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)
    frame_ready = pyqtSignal(str)   # ← ADD THIS — emits path to each heatmap PNG


    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path


    def run(self):
        try:
            url = f"{API}/predict"
            with open(self.image_path, "rb") as f:
                ext = os.path.splitext(self.image_path)[1].lower()
                files = {"file": (os.path.basename(self.image_path), f, "video/mp4")}
                response = requests.post(url, files=files, timeout=600)

            if response.status_code == 200:
                self.finished.emit(response.json())
            else:
                self.error.emit(f"Server returned {response.status_code}: {response.text}")
        except requests.exceptions.ConnectionError:
            self.error.emit("Cannot connect to server.\nPlease restart GastroVision. If this keeps happening, use Send feedback.")
        except Exception as e:
            self.error.emit(str(e))

        


# ─────────────────────────────────────────────
#  DIVIDER
# ─────────────────────────────────────────────
def h_divider():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #1e2230; border: none; border-top: 1px solid #1e2230;")
    return line


# ─────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────
LABELS = [
    "dyed-lifted-polyps",
    "dyed-resection-margins",
    "esophagitis",
    "normal-cecum",
    "normal-pylorus",
    "normal-z-line",
    "polyps",
    "ulcerative-colitis",
]

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"GastroVision v{VERSION} - research prototype")
        self.resize(1100, 760)
        self.setMinimumSize(900, 640)
        self.setStyleSheet(QSS)

        self.selected_image_path = None
        self.worker = None

        self._preview_timer = QTimer()
        self._preview_timer.timeout.connect(self._next_preview_frame)
        self._preview_frames = []   # list of image paths to cycle
        self._preview_idx = 0

        self._frame_counter = 0
        self._frame_timer = QTimer()
        self._frame_timer.timeout.connect(self._update_frame_display)

        self._scan_timer = QTimer()
        self._scan_timer.timeout.connect(self._scan_for_frames)
        self._scan_path = ""

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_body(), 1)
        root_layout.addWidget(self._build_footer())

    def _send_feedback(self):
        """Copy anonymous diagnostics to the clipboard and open the feedback form."""
        QGuiApplication.clipboard().setText(diagnostics())
        QMessageBox.information(
            self, "Send feedback",
            "Your browser will open the feedback form.\n\n"
            "A few technical details (app version, operating system) were copied to your clipboard - "
            "please paste them into the form.\n\n"
            "Do NOT upload or describe patient-identifying information.")
        QDesktopServices.openUrl(QUrl(FEEDBACK_URL))

    # ── Header ───────────────────────────────
    def _build_header(self):
        header = QWidget()
        header.setObjectName("Header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)

        left = QVBoxLayout()
        left.setSpacing(1)
        title = QLabel(f"GASTROVISION V{VERSION}")
        title.setObjectName("AppTitle")
        sub = QLabel("GI FINDING DETECTION  //  RESEARCH PROTOTYPE")
        sub.setObjectName("AppSubtitle")
        left.addWidget(title)
        left.addWidget(sub)
        hl.addLayout(left)
        hl.addStretch()

        fb = QPushButton("SEND FEEDBACK")
        fb.setObjectName("ClearBtn")
        fb.setCursor(Qt.CursorShape.PointingHandCursor)
        fb.clicked.connect(self._send_feedback)
        hl.addWidget(fb)

        status = QLabel("● SERVER: READY")
        status.setObjectName("StatusDot")
        hl.addWidget(status)
        return header

    # ── Body ──────────────────────────────────
    def _build_body(self):
        body = QWidget()
        body.setObjectName("Root")
        bl = QHBoxLayout(body)
        bl.setContentsMargins(20, 20, 20, 20)
        bl.setSpacing(16)

        bl.addLayout(self._build_left_panel(), 3)
        bl.addLayout(self._build_right_panel(), 2)
        return body

    # ── Left Panel (upload + run) ─────────────
    def _build_left_panel(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Section title
        t = QLabel("// VIDEO INPUT")
        t.setObjectName("SectionTitle")
        layout.addWidget(t)

        # Image preview box
        self.image_box = QFrame()
        self.image_box.setObjectName("ImageBox")
        img_box_layout = QVBoxLayout(self.image_box)
        img_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.placeholder_label = QLabel("[ DROP OR SELECT AN VIDEO ]")
        self.placeholder_label.setObjectName("PlaceholderLabel")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        img_box_layout.addWidget(self.placeholder_label)
        img_box_layout.addWidget(self.image_preview)
        self.image_preview.hide()
        layout.addWidget(self.image_box, 1)

        # Buttons row
        btn_row = QHBoxLayout()
        self.upload_btn = QPushButton("⊞  SELECT VIDEO")
        self.upload_btn.setObjectName("UploadBtn")
        self.upload_btn.clicked.connect(self.pick_image)
        btn_row.addWidget(self.upload_btn)

        self.clear_btn = QPushButton("CLEAR")
        self.clear_btn.setObjectName("ClearBtn")
        self.clear_btn.clicked.connect(self.clear_all)
        self.clear_btn.setEnabled(False)
        btn_row.addWidget(self.clear_btn)
        layout.addLayout(btn_row)

        layout.addWidget(h_divider())

        # Progress section
        t2 = QLabel("// INFERENCE PIPELINE")
        t2.setObjectName("SectionTitle")
        layout.addWidget(t2)

        self.status_label = QLabel("IDLE — SELECT A VIDEO TO BEGIN")
        self.status_label.setObjectName("BodyLabel")
        layout.addWidget(self.status_label)

        self.pbar = QProgressBar()
        self.pbar.setValue(0)
        self.pbar.setTextVisible(False)
        self.pbar.setMaximumHeight(6)
        layout.addWidget(self.pbar)

        self.exec_btn = QPushButton("⚡  EXECUTE ANALYSIS SEQUENCE")
        self.exec_btn.setObjectName("ExecuteBtn")
        self.exec_btn.clicked.connect(self.run_analysis)
        self.exec_btn.setEnabled(False)
        layout.addWidget(self.exec_btn)

        return layout

    # ── Right Panel (results + classes) ───────
    def _build_right_panel(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)

        t = QLabel("// ANALYSIS OUTPUT")
        t.setObjectName("SectionTitle")
        layout.addWidget(t)

        # Result display card
        self.result_card = QFrame()
        self.result_card.setObjectName("Card")
        rc_layout = QVBoxLayout(self.result_card)
        rc_layout.setContentsMargins(20, 20, 20, 20)
        rc_layout.setSpacing(8)

        awaiting = QLabel("AWAITING INPUT...")
        awaiting.setObjectName("PlaceholderLabel")
        awaiting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rc_layout.addWidget(awaiting, alignment=Qt.AlignmentFlag.AlignCenter)

        self.result_inner = rc_layout
        self.awaiting_label = awaiting

        self.result_title = QLabel("")
        self.result_title.setObjectName("ResultLabel")
        self.result_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_title.setWordWrap(True)
        self.result_title.hide()
        rc_layout.addWidget(self.result_title)

        self.result_sub = QLabel("PREDICTED CLASS")
        self.result_sub.setObjectName("ResultSubLabel")
        self.result_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_sub.hide()  
        rc_layout.addWidget(self.result_sub)

        self.confidence_label = QLabel("")
        self.confidence_label.setObjectName("ResultSubLabel")
        self.confidence_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.confidence_label.hide()
        rc_layout.addWidget(self.confidence_label)

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        rc_layout.addWidget(self.error_label)

        layout.addWidget(self.result_card)

        # File properties
        t2 = QLabel("// FILE PROPERTIES")
        t2.setObjectName("SectionTitle")
        layout.addWidget(t2)

        prop_card = QFrame()
        prop_card.setObjectName("Card")
        prop_layout = QGridLayout(prop_card)
        prop_layout.setContentsMargins(16, 12, 16, 12)
        prop_layout.setHorizontalSpacing(16)
        prop_layout.setVerticalSpacing(6)

        keys = ["FILENAME", "FORMAT", "SIZE", "PATH"]
        self.prop_vals = {}
        for i, k in enumerate(keys):
            lbl_k = QLabel(k + ":")
            lbl_k.setObjectName("PropKey")
            lbl_v = QLabel("—")
            lbl_v.setObjectName("PropVal")
            lbl_v.setWordWrap(True)
            prop_layout.addWidget(lbl_k, i, 0)
            prop_layout.addWidget(lbl_v, i, 1)
            self.prop_vals[k] = lbl_v

        layout.addWidget(prop_card)

        # Known classes
        t3 = QLabel("// KNOWN CLASSES")
        t3.setObjectName("SectionTitle")
        layout.addWidget(t3)

        class_card = QFrame()
        class_card.setObjectName("Card")
        class_inner = QVBoxLayout(class_card)
        class_inner.setContentsMargins(12, 12, 12, 12)
        class_inner.setSpacing(6)

        self.class_chips = {}
        for label in LABELS:
            chip = QLabel(label)
            chip.setObjectName("ClassChip")
            chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            class_inner.addWidget(chip)
            self.class_chips[label] = chip

        layout.addWidget(class_card, 1)

        return layout

    # ── Footer ────────────────────────────────
    def _build_footer(self):
        footer = QWidget()
        footer.setObjectName("Footer")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        for text in ["READY — SYSTEM_OK: 200", "EfficientNetV2 · Kvasir + HyperKvasir", "ONNX Runtime", "RESEARCH PROTOTYPE — NOT A MEDICAL DEVICE"]:
            lbl = QLabel(text)
            lbl.setObjectName("FooterLabel")
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setStyleSheet("color: #ffffff55;")
            fl.addWidget(lbl)
            fl.addWidget(sep)

        fl.addStretch()
        ver = QLabel(f"v{VERSION} — GASTROVISION")
        ver.setObjectName("FooterLabel")
        fl.addWidget(ver)
        return footer

    # ─────────────────────────────────────────
    #  SLOTS
    # ─────────────────────────────────────────
    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select GI Video", "",
            "Video Files (*.mp4 *.avi *.mkv);;All Files (*)"
        )
        if not path:
            return

        self.selected_image_path = path
        self._show_preview(path)
        self._update_props(path)
        self._reset_results()

        self.upload_btn.setText("⊞  CHANGE VIDEO")
        self.clear_btn.setEnabled(True)
        self.exec_btn.setEnabled(True)
        self.status_label.setText("VIDEO LOADED — READY TO ANALYSE")

    def _show_preview(self, path):
        px = QPixmap(path)
        if not px.isNull():
            px = px.scaled(
                self.image_box.width() - 20,
                self.image_box.height() - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_preview.setPixmap(px)
            self.image_preview.show()
            self.placeholder_label.hide()
            self.image_box.setProperty("hasImage", True)
            self.image_box.style().unpolish(self.image_box)
            self.image_box.style().polish(self.image_box)

    
    def _scan_for_frames(self):
        if not self._scan_path or not os.path.exists(self._scan_path):
            return
        found = sorted([
            os.path.join(self._scan_path, f)
            for f in os.listdir(self._scan_path)
            if f.endswith(".png")
        ])
        if found:
            self._preview_frames = found

    def _next_preview_frame(self):
        if not self._preview_frames:
            # No frames yet — pulse the placeholder text
            dots = getattr(self, '_dot_count', 0)
            self._dot_count = (dots + 1) % 4
            self.placeholder_label.setText("PROCESSING" + "." * self._dot_count)
            self.placeholder_label.show()
            return

        path = self._preview_frames[self._preview_idx % len(self._preview_frames)]
        self._preview_idx += 1
        px = QPixmap(path)
        if not px.isNull():
            px = px.scaled(
                self.image_box.width() - 20,
                self.image_box.height() - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_preview.setPixmap(px)
            self.image_preview.show()
            self.placeholder_label.hide()

    
    # Add new method:
    def _poll_heatmaps(self, filename):
        video_name = os.path.splitext(filename)[0]
        try:
            resp = requests.get(f"{API}/heatmaps/{video_name}", timeout=2)
            if resp.status_code == 200:
                body = resp.json()
                paths = body.get("heatmap_paths", [])
                if body.get("done") or len(paths) >= 5:  # finished (possibly with fewer than 5)
                    self._heatmap_poll_timer.stop()
                    if paths:
                        self._preview_frames = paths
                        self._preview_idx = 0
                        self._preview_timer.start(1500)
                    else:
                        self._preview_timer.stop()
                        self.placeholder_label.setText("NO HEATMAPS (NO FINDING)")
        except Exception:
            pass

    def _update_props(self, path):
        from PIL import Image as PILImage
        fname = os.path.basename(path)
        ext = os.path.splitext(fname)[1].upper().lstrip(".")
        size_kb = os.path.getsize(path) / 1024

        self.prop_vals["FILENAME"].setText(fname)
        self.prop_vals["FORMAT"].setText(ext)
        self.prop_vals["SIZE"].setText(f"{size_kb / 1024:.2f} MB")
        self.prop_vals["PATH"].setText(os.path.dirname(path))

    def _update_frame_display(self):
        self._frame_counter += 1
        self.status_label.setText(f"PROCESSING FRAME {self._frame_counter}...")
        self.awaiting_label.setText(f"ANALYSING FRAME {self._frame_counter}")

    def _reset_results(self):
        self.result_card.setObjectName("Card")
        self.result_card.style().unpolish(self.result_card)
        self.result_card.style().polish(self.result_card)

        self.awaiting_label.setText("AWAITING INPUT...")
        self.awaiting_label.show()
        self.result_title.hide()
        self.result_sub.hide()
        self.error_label.hide()
        self.confidence_label.hide()

        for chip in self.class_chips.values():
            chip.setObjectName("ClassChip")
            chip.style().unpolish(chip)
            chip.style().polish(chip)

    def clear_all(self):
        # Stop all timers
        self._preview_timer.stop()
        self._frame_timer.stop()
        self._scan_timer.stop()
        if hasattr(self, '_heatmap_poll_timer'):
            self._heatmap_poll_timer.stop()

        # Handle worker
        if self.worker and self.worker.isRunning():
            try:
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except TypeError:
                pass # signals were not connected or already disconnected
            self.worker.terminate() # forceful stop since it's just a web request
            self.worker.wait()

        self.selected_image_path = None
        self._preview_frames = []
        self._preview_idx = 0
        self._scan_path = ""
        
        self.image_preview.clear()
        self.image_preview.hide()
        
        self.placeholder_label.setText("[ DROP OR SELECT AN VIDEO ]")
        self.placeholder_label.show()
        self.image_box.setProperty("hasImage", False)
        self.image_box.style().unpolish(self.image_box)
        self.image_box.style().polish(self.image_box)

        for k in self.prop_vals:
            self.prop_vals[k].setText("—")

        self.upload_btn.setText("⊞  SELECT VIDEO")
        self.upload_btn.setEnabled(True)
        self.clear_btn.setEnabled(False)
        self.exec_btn.setEnabled(False)
        self.status_label.setText("IDLE — SELECT A VIDEO TO BEGIN")
        self.pbar.setValue(0)
        self.pbar.setRange(0, 100)
        self._reset_results()

    def run_analysis(self):
        if not self.selected_image_path:
            return

        # Lock UI
        self.exec_btn.setEnabled(False)
        self.upload_btn.setEnabled(False)
        self.clear_btn.setEnabled(True)  # Keep clear enabled for cancellation
        self.pbar.setRange(0, 0)
        self._frame_counter = 0
        self._frame_timer.start(150)     # marquee
        self.status_label.setText("RUNNING INFERENCE ON ONNX MODEL...")
        self._reset_results()
        self.awaiting_label.setText("PROCESSING...")

        self._preview_frames = []
        self._preview_idx = 0
        self._preview_timer.start(120)
        video_name = os.path.splitext(os.path.basename(self.selected_image_path))[0]
   # ~8fps cycling
        # Point to where backend writes cleaned frames
        self._scan_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),  # adjust if needed
            "..", "backend", "outputs", video_name, "cleaned_frames"
        )
        self._scan_timer.start(500)

        self.worker = AnalysisWorker(self.selected_image_path)
        self.worker.finished.connect(self._on_success)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_success(self, result):
        self._frame_timer.stop()

        self._preview_timer.stop()

        self._scan_timer.stop()

        self._heatmap_poll_timer = QTimer()
        self._heatmap_poll_timer.timeout.connect(
            lambda: self._poll_heatmaps(result.get("file", ""))
        )
        self._heatmap_poll_timer.start(2000)


        heatmap_paths = result.get("heatmap_paths", [])   # your backend must return these
        if heatmap_paths:
            self._preview_frames = heatmap_paths
            self._preview_idx = 0
            self._preview_timer.start(1500)   # slow cycle — 1.5s per heatmap frame
            self._unlock_ui()
        prediction = result.get("label", "unknown")
        confidence = result.get("confidence", 0.0)

        # Card colour
        self.result_card.setObjectName("ResultCard")
        self.result_card.style().unpolish(self.result_card)
        self.result_card.style().polish(self.result_card)

        # Labels
        self.awaiting_label.hide()
        self.result_title.setText(prediction.upper().replace("-", " "))
        self.result_title.show()
        self.result_sub.show()
        self.error_label.hide()

        if prediction == "no-finding":
            unc = result.get("uncertain_fraction", 1.0)
            self.confidence_label.setText(
                f"NO CONSISTENT FINDING  ({unc * 100:.0f}% OF FRAMES UNCERTAIN / NON-TARGET)\n"
                "NOT A CLEARANCE: THE MODEL ONLY KNOWS 8 FINDINGS")
        else:
            txt = f"MEAN CONFIDENCE: {confidence * 100:.1f}%"
            fl = result.get("findings", []) or []
            if fl and fl[0].get("strength") == "possible":
                txt += "\nPOSSIBLE FINDING - BELOW THE STANDARD CONFIDENCE BAR, PLEASE REVIEW"
            if len(fl) > 1:
                txt += "\nALSO SEEN: " + ", ".join(
                    f"{f['class'].upper()}" + (" (POSSIBLE)" if f.get("strength") == "possible" else "") for f in fl[1:])
            self.confidence_label.setText(txt)
        self.confidence_label.show()

        # Highlight matching chip
        for label, chip in self.class_chips.items():
            if label == prediction:
                chip.setObjectName("ClassChipActive")
            else:
                chip.setObjectName("ClassChip")
            chip.style().unpolish(chip)
            chip.style().polish(chip)

        self.pbar.setRange(0, 100)
        self.pbar.setValue(100)
        self.status_label.setText("ANALYSIS COMPLETE — PREDICTION READY")

    def _on_error(self, message):
        self._frame_timer.stop()
        self._scan_timer.stop()


        self._unlock_ui()

        self.result_card.setObjectName("ErrorCard")
        self.result_card.style().unpolish(self.result_card)
        self.result_card.style().polish(self.result_card)

        self.awaiting_label.hide()
        self.error_label.setText(f"ERROR:\n{message}")
        self.error_label.show()
        self.result_title.hide()
        self.result_sub.hide()

        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.status_label.setText("ANALYSIS FAILED — SEE ERROR OUTPUT")

    def _unlock_ui(self):
        self.exec_btn.setEnabled(True)
        self.upload_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())