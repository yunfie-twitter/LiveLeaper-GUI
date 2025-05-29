import sys
import os
import subprocess
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QFileDialog, QVBoxLayout, QHBoxLayout, QCheckBox,
    QProgressBar, QMessageBox, QComboBox, QToolButton, QDialog
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon

CONFIG_FILE = "config.txt"
EXE_FILE = "liveleaper_core.exe"


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(300, 120)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Language (not yet implemented):"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["English", "日本語"])
        layout.addWidget(self.lang_combo)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.setLayout(layout)


class LiveLeaperGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiveLeaper")
        self.setFixedSize(400, 360)
        self.setStyleSheet("""
            QWidget {
                background-color: #2e2e2e;
                color: white;
                font-size: 14px;
            }
            QLineEdit, QComboBox {
                background-color: #3c3c3c;
                color: white;
                border: 1px solid #5a5a5a;
                padding: 4px;
            }
            QPushButton, QToolButton {
                background-color: #444;
                border: 1px solid #666;
                padding: 6px;
            }
            QPushButton:hover, QToolButton:hover {
                background-color: #555;
            }
            QCheckBox {
                padding-top: 8px;
            }
        """)
        self.init_ui()
        self.load_config()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(10)

        gear_button = QToolButton()
        gear_button.setIcon(QIcon("gear_icon.png"))
        gear_button.setIconSize(QSize(24, 24))
        gear_button.setStyleSheet("border: none;")
        gear_button.clicked.connect(self.open_settings)

        header_layout = QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(gear_button)
        layout.addLayout(header_layout)

        layout.addWidget(QLabel("YouTube URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=XXXXXXXXXXX")
        self.url_input.setFixedHeight(28)
        layout.addWidget(self.url_input)

        layout.addWidget(QLabel("Destination folder:"))
        self.output_input = QLineEdit()
        self.output_input.setFixedHeight(28)
        output_btn = QPushButton("Browse...")
        output_btn.setFixedHeight(28)
        output_btn.setFixedWidth(80)
        output_btn.clicked.connect(self.browse_output)

        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_input)
        output_layout.addWidget(output_btn)
        layout.addLayout(output_layout)

        layout.addWidget(QLabel("Output format:"))
        self.ext_select = QComboBox()
        self.ext_select.addItems(["mp4", "webm", "mp3", "m4a"])
        self.ext_select.setFixedHeight(28)
        layout.addWidget(self.ext_select)

        self.audio_checkbox = QCheckBox("Extract audio only")
        layout.addWidget(self.audio_checkbox)

        self.download_button = QPushButton("Download")
        self.download_button.setFixedHeight(36)
        self.download_button.clicked.connect(self.run_download)
        layout.addWidget(self.download_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.output_input.setText(folder)

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec_()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        if k == "output":
                            self.output_input.setText(v)
                        elif k == "ext":
                            index = self.ext_select.findText(v)
                            if index >= 0:
                                self.ext_select.setCurrentIndex(index)
                        elif k == "audio":
                            self.audio_checkbox.setChecked(v.lower() == "true")

    def save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(f"output={self.output_input.text()}\n")
            f.write(f"ext={self.ext_select.currentText()}\n")
            f.write(f"audio={str(self.audio_checkbox.isChecked()).lower()}\n")

    def run_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a YouTube URL.")
            return

        self.save_config()
        cmd = [EXE_FILE, url,
               "--output", self.output_input.text(),
               "--ext", self.ext_select.currentText()]
        if self.audio_checkbox.isChecked():
            cmd.append("--audio")

        self.download_button.setEnabled(False)
        self.progress_bar.setVisible(True)

        def task():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    QMessageBox.information(self, "Success", "Download completed.")
                else:
                    QMessageBox.critical(self, "Error", result.stderr)
            finally:
                self.download_button.setEnabled(True)
                self.progress_bar.setVisible(False)

        threading.Thread(target=task, daemon=True).start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = LiveLeaperGUI()
    gui.show()
    sys.exit(app.exec_())
