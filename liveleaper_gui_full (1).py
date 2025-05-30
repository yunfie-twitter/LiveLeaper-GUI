import sys
import os
import uuid
import threading
import subprocess
import time
import webbrowser
import shutil
import psutil
from queue import Queue

from flask import Flask, request, send_file, Response, stream_with_context

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel
)
from PyQt5.QtCore import Qt

SHOW_GUI = "--console" not in sys.argv

app = Flask(__name__)
TEMP_DIR = "temp_downloads"
os.makedirs(TEMP_DIR, exist_ok=True)

log_queue = Queue()
latest_file_path = None


class LogWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiveLeaper Server")
        self.setGeometry(300, 300, 700, 500)

        self.layout = QVBoxLayout()
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.layout.addWidget(self.log_area)

        self.sys_info = QLabel()
        self.layout.addWidget(self.sys_info)

        btn_layout = QHBoxLayout()
        self.copy_btn = QPushButton("ログをコピー")
        self.save_btn = QPushButton("ログを保存")
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.save_btn)
        self.layout.addLayout(btn_layout)

        self.setLayout(self.layout)

        self.copy_btn.clicked.connect(self.copy_log)
        self.save_btn.clicked.connect(self.save_log)

        self.update_timer = threading.Timer(1, self.update_system_info)
        self.update_timer.start()

    def append_log(self, text):
        self.log_area.append(text)

    def copy_log(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.log_area.toPlainText())

    def save_log(self):
        with open("liveleaper_log.txt", "w", encoding="utf-8") as f:
            f.write(self.log_area.toPlainText())

    def update_system_info(self):
        if self.isVisible():
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            self.sys_info.setText(f"CPU使用率: {cpu:.1f}% | メモリ使用率: {mem:.1f}%")
            threading.Timer(1, self.update_system_info).start()


log_window = None
app_qt = None


def run_process(args, output_dir):
    global latest_file_path
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in iter(process.stdout.readline, ''):
        line = line.strip()
        print(line)
        if log_window:
            log_window.append_log(line)
        log_queue.put(line)
    process.stdout.close()
    process.wait()

    files = os.listdir(output_dir)
    if files:
        latest_file_path = os.path.join(output_dir, files[0])
    log_queue.put("[[DL_COMPLETE]]")


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        urls = request.form["urls"].split()
        audio = "audio" in request.form
        ext = request.form.get("ext", "mp4")
        info = "info" in request.form

        output = os.path.join(TEMP_DIR, str(uuid.uuid4()))
        os.makedirs(output, exist_ok=True)

        args = ["LiveLeaper_Core.exe"] + urls
        if audio:
            args.append("--audio")
        if info:
            args.append("--info")
        args += ["--ext", ext, "--output", output]

        threading.Thread(target=run_process, args=(args, output), daemon=True).start()
        return "", 200

    html = f"""
    <!DOCTYPE html>
    <html><head><title>LiveLeaper GUI</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/vue@2/dist/vue.js"></script>
    <style>
        body {{font-family: sans-serif; margin-top: 40px;}}
        .container {{max-width: 800px;}}
        pre {{background-color: #f8f9fa; padding: 1em; height: 300px; overflow-y: scroll;}}
    </style></head>
    <body><div id="app" class="container">
    <h1 class="text-center">🎬 LiveLeaper ダウンローダー</h1>
    <form @submit.prevent="submitForm">
        <div class="mb-3"><label>URL(s)</label>
        <input type="text" class="form-control" v-model="urls" required></div>

        <div class="form-check mb-3">
            <input class="form-check-input" type="checkbox" v-model="audio">
            <label class="form-check-label">音声のみ</label>
        </div>

        <div class="mb-3"><label>拡張子</label>
        <input type="text" class="form-control" v-model="ext"></div>

        <div class="form-check mb-3">
            <input class="form-check-input" type="checkbox" v-model="info">
            <label class="form-check-label">情報のみ取得</label>
        </div>

        <button type="submit" class="btn btn-primary w-100" :disabled="downloading">
            {{ downloading ? "ダウンロード中..." : "ダウンロード開始" }}
        </button>
    </form>

    <div class="mt-4">
        <h5>出力ログ:</h5>
        <pre>{{ logs }}</pre>
    </div>

    <div class="alert alert-success mt-3" v-if="completed">
        ✅ ダウンロードが完了しました。
        <br><a :href="'/download'" class="btn btn-success mt-2">ファイルをダウンロード</a>
    </div>

    </div><script>
    new Vue({{
        el: '#app',
        data: {{
            urls: '',
            audio: false,
            ext: 'mp4',
            info: false,
            logs: '',
            downloading: false,
            completed: false
        }},
        methods: {{
            submitForm() {{
                this.logs = '';
                this.downloading = true;
                this.completed = false;

                fetch("/", {{
                    method: "POST",
                    headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                    body: new URLSearchParams({{
                        urls: this.urls,
                        audio: this.audio ? "on" : "",
                        ext: this.ext,
                        info: this.info ? "on" : ""
                    }})
                }});

                const eventSource = new EventSource("/stream");
                eventSource.onmessage = (e) => {{
                    if (e.data === "[[DL_COMPLETE]]") {{
                        this.downloading = false;
                        this.completed = true;
                        eventSource.close();
                    }} else {{
                        this.logs += e.data + "\n";
                    }}
                }};
            }}
        }}
    }});
    </script></body></html>
    """
    return Response(html, mimetype='text/html')


@app.route("/stream")
def stream():
    def generate():
        while True:
            line = log_queue.get()
            yield f"data: {line}

"
            if line == "[[DL_COMPLETE]]":
                break
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route("/download")
def download():
    if latest_file_path and os.path.exists(latest_file_path):
        return send_file(latest_file_path, as_attachment=True)
    return "ファイルが存在しません", 404


def open_browser():
    webbrowser.open("http://127.0.0.1:5000")


def cleanup_temp_files():
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)


def main():
    global app_qt, log_window
    if SHOW_GUI:
        app_qt = QApplication(sys.argv)
        log_window = LogWindow()
        log_window.show()
        threading.Thread(target=lambda: app.run(debug=False, threaded=True), daemon=True).start()
        threading.Timer(1.0, open_browser).start()
        app_qt.aboutToQuit.connect(cleanup_temp_files)
        sys.exit(app_qt.exec_())
    else:
        threading.Timer(1.0, open_browser).start()
        app.run(debug=False, threaded=True)


if __name__ == "__main__":
    main()
