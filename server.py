#!/usr/bin/env python3
"""
Threads 圖片下載器 — 本機 Web UI
用法：python3 server.py
開啟 http://localhost:8765
"""
import json
import os
import queue
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

app = Flask(__name__)

# job_id -> {"status": "running"|"done"|"error", "images": [...], "log": [...]}
JOBS: dict[str, dict] = {}

HTML = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Threads 圖片下載器</title>
<style>
:root {
  --bg: #faf9f5;
  --card: #ffffff;
  --border: #e8e6dc;
  --text: #141413;
  --muted: #8a8679;
  --accent: #d97757;
  --green: #3d9970;
  --red: #c0392b;
  --radius: 12px;
  --mono: 'SF Mono', 'Fira Code', monospace;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', -apple-system, sans-serif;
  min-height: 100vh;
  padding: 40px 20px;
}
.wrap { max-width: 760px; margin: 0 auto; }
h1 { font-size: 1.8rem; font-weight: 800; letter-spacing: -0.5px; }
.sub { color: var(--muted); font-size: 0.82rem; margin-top: 6px; margin-bottom: 32px; }

.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 20px;
}
label { font-size: 0.85rem; font-weight: 600; display: block; margin-bottom: 6px; }
input[type="url"], input[type="number"] {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 0.95rem;
  font-family: inherit;
  background: var(--bg);
  outline: none;
  transition: border-color 0.15s;
}
input:focus { border-color: var(--accent); }

.row { display: flex; gap: 16px; align-items: flex-end; margin-top: 16px; }
.row .field { flex: 1; }
.row .field-sm { width: 120px; flex: none; }

.opt-row { display: flex; align-items: center; gap: 8px; margin-top: 14px; }
.opt-row input[type="checkbox"] { width: 16px; height: 16px; accent-color: var(--accent); cursor: pointer; }
.opt-row label { margin: 0; font-weight: 400; color: var(--muted); cursor: pointer; }

button {
  padding: 11px 28px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
  white-space: nowrap;
}
button:hover { opacity: 0.88; }
button:disabled { opacity: 0.45; cursor: not-allowed; }

#log-box {
  background: #1a1a1a;
  color: #d4d4d4;
  font-family: var(--mono);
  font-size: 0.8rem;
  line-height: 1.7;
  padding: 16px;
  border-radius: 8px;
  min-height: 120px;
  max-height: 320px;
  overflow-y: auto;
  white-space: pre-wrap;
  display: none;
}
#log-box.show { display: block; }
.log-ok   { color: #4ec9b0; }
.log-skip { color: #808080; }
.log-err  { color: #f48771; }
.log-info { color: #9cdcfe; }

#gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-top: 4px;
}
.thumb-wrap {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border);
  aspect-ratio: 1;
  background: var(--bg);
  position: relative;
}
.thumb-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  cursor: pointer;
  transition: opacity 0.15s;
}
.thumb-wrap img:hover { opacity: 0.85; }
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  margin-bottom: 12px;
}
.badge.running { background: #fff8e1; color: #b8860b; }
.badge.done    { background: #e8f5e9; color: #2e7d32; }
.badge.error   { background: #fce4e4; color: var(--red); }
#status-section { display: none; }
#status-section.show { display: block; }

/* lightbox */
#lightbox {
  display: none;
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.88);
  z-index: 999;
  align-items: center;
  justify-content: center;
}
#lightbox.show { display: flex; }
#lightbox img { max-width: 90vw; max-height: 90vh; border-radius: 6px; }
#lightbox-close {
  position: fixed; top: 20px; right: 24px;
  color: #fff; font-size: 2rem; cursor: pointer; line-height: 1;
}
</style>
</head>
<body>
<div class="wrap">
  <h1>Threads 圖片下載器</h1>
  <p class="sub">貼上 Threads 貼文 URL，自動抓取貼文中的所有圖片</p>

  <div class="card">
    <label for="url-input">貼文 URL</label>
    <div class="row">
      <div class="field">
        <input type="url" id="url-input" placeholder="https://www.threads.net/@xxx/post/..." />
      </div>
      <div class="field-sm">
        <label for="min-size">最小邊長 (px)</label>
        <input type="number" id="min-size" value="200" min="50" max="2000" />
      </div>
    </div>
    <div class="opt-row">
      <input type="checkbox" id="headless" />
      <label for="headless">無瀏覽器視窗模式（headless）</label>
    </div>
    <div class="opt-row">
      <input type="checkbox" id="login" />
      <label for="login">先登入 Threads（首次使用勾選）</label>
    </div>
    <div style="margin-top:20px">
      <button id="btn-start" onclick="startDownload()">開始下載</button>
    </div>
  </div>

  <div id="status-section" class="card">
    <span class="badge" id="badge">執行中</span>
    <div id="log-box"></div>
    <div id="gallery-wrap" style="margin-top:16px; display:none">
      <p style="font-size:0.85rem;color:var(--muted);margin-bottom:12px" id="gallery-label"></p>
      <div id="gallery"></div>
    </div>
  </div>
</div>

<div id="lightbox" onclick="closeLightbox()">
  <span id="lightbox-close" onclick="closeLightbox()">×</span>
  <img id="lightbox-img" src="" />
</div>

<script>
let evtSource = null;

function startDownload() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) { alert('請輸入 Threads 貼文 URL'); return; }

  // reset UI
  const logBox = document.getElementById('log-box');
  const gallery = document.getElementById('gallery');
  const section = document.getElementById('status-section');
  logBox.innerHTML = '';
  gallery.innerHTML = '';
  logBox.className = 'show';
  section.className = 'show';
  document.getElementById('gallery-wrap').style.display = 'none';
  setBadge('running', '執行中...');
  document.getElementById('btn-start').disabled = true;

  if (evtSource) evtSource.close();

  const params = new URLSearchParams({
    url,
    min_size: document.getElementById('min-size').value,
    headless: document.getElementById('headless').checked ? '1' : '0',
    login: document.getElementById('login').checked ? '1' : '0',
  });

  evtSource = new EventSource('/stream?' + params.toString());

  evtSource.onmessage = (e) => {
    const data = JSON.parse(e.data);

    if (data.log) {
      const line = document.createElement('div');
      line.textContent = data.log;
      if (data.log.includes('✅')) line.className = 'log-ok';
      else if (data.log.includes('⏭️')) line.className = 'log-skip';
      else if (data.log.includes('❌')) line.className = 'log-err';
      else line.className = 'log-info';
      logBox.appendChild(line);
      logBox.scrollTop = logBox.scrollHeight;
    }

    if (data.done) {
      evtSource.close();
      document.getElementById('btn-start').disabled = false;
      if (data.images && data.images.length > 0) {
        setBadge('done', `完成！共 ${data.images.length} 張`);
        renderGallery(data.images, data.folder);
      } else {
        setBadge('done', '完成（沒有找到圖片）');
      }
    }

    if (data.error) {
      evtSource.close();
      document.getElementById('btn-start').disabled = false;
      setBadge('error', '發生錯誤');
    }
  };

  evtSource.onerror = () => {
    evtSource.close();
    document.getElementById('btn-start').disabled = false;
    setBadge('error', '連線中斷');
  };
}

function setBadge(type, text) {
  const b = document.getElementById('badge');
  b.className = 'badge ' + type;
  b.textContent = text;
}

function renderGallery(images, folder) {
  const wrap = document.getElementById('gallery-wrap');
  const gallery = document.getElementById('gallery');
  document.getElementById('gallery-label').textContent =
    `下載的圖片（點擊放大）— 存在 ${folder}/`;
  gallery.innerHTML = '';
  images.forEach(img => {
    const div = document.createElement('div');
    div.className = 'thumb-wrap';
    const el = document.createElement('img');
    el.src = '/img/' + encodeURIComponent(img);
    el.loading = 'lazy';
    el.onclick = () => openLightbox('/img/' + encodeURIComponent(img));
    div.appendChild(el);
    gallery.appendChild(div);
  });
  wrap.style.display = 'block';
}

function openLightbox(src) {
  document.getElementById('lightbox-img').src = src;
  document.getElementById('lightbox').className = 'show';
}
function closeLightbox() {
  document.getElementById('lightbox').className = '';
  document.getElementById('lightbox-img').src = '';
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });
</script>
</body>
</html>
"""


def run_download(job_id: str, url: str, headless: bool, login: bool, min_size: int):
    """在背景 thread 執行下載腳本，把 stdout 推進 job queue。"""
    job = JOBS[job_id]
    q = job["queue"]

    script = Path(__file__).parent / "scripts" / "download_threads_images.py"
    cmd = [sys.executable, str(script), url, "--min-size", str(min_size)]
    if headless:
        cmd.append("--headless")
    if login:
        cmd.append("--login")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                job["log"].append(line)
                q.put({"log": line})

        proc.wait()

        # 找出下載資料夾和圖片
        m = re.search(r"threads\.(?:net|com)/@([^/]+)/post/([^/?#]+)", url)
        images = []
        folder = ""
        if m:
            folder = f"{m.group(1)}_{m.group(2)}"
            folder_path = Path(__file__).parent / folder
            if folder_path.exists():
                images = sorted(
                    f"{folder}/{f.name}"
                    for f in folder_path.iterdir()
                    if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
                )

        job["status"] = "done"
        job["images"] = images
        q.put({"done": True, "images": images, "folder": folder})

    except Exception as e:
        job["status"] = "error"
        q.put({"log": f"❌ 執行失敗: {e}", "error": True, "done": True})


@app.route("/")
def index():
    return HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/stream")
def stream():
    url = request.args.get("url", "")
    headless = request.args.get("headless") == "1"
    login = request.args.get("login") == "1"
    min_size = int(request.args.get("min_size", 200))

    if not url:
        return jsonify({"error": "missing url"}), 400

    job_id = str(uuid.uuid4())
    q: queue.Queue = queue.Queue()
    JOBS[job_id] = {"status": "running", "log": [], "images": [], "queue": q}

    t = threading.Thread(
        target=run_download, args=(job_id, url, headless, login, min_size), daemon=True
    )
    t.start()

    def generate():
        while True:
            try:
                msg = q.get(timeout=60)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg.get("done"):
                    break
            except queue.Empty:
                yield "data: {}\n\n"  # heartbeat

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/img/<path:filepath>")
def serve_image(filepath: str):
    """供前端預覽用的圖片路由。"""
    base = Path(__file__).parent
    # 只允許存取下載資料夾（避免任意路徑存取）
    full = (base / filepath).resolve()
    if not str(full).startswith(str(base.resolve())):
        return "forbidden", 403
    return send_from_directory(str(base), filepath)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print(f"\n🚀 Threads 圖片下載器")
    print(f"   開啟瀏覽器：http://localhost:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
