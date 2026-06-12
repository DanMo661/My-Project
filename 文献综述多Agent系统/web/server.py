"""文献综述系统 Web 服务 — Flask + SSE 实时进度"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

app = Flask(__name__, static_folder="static")

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
LOG_FILE = OUTPUT_DIR / "pipeline.log"

progress_queue = queue.Queue()
pipeline_state = {"running": False, "stage": -1, "detail": "", "output": ""}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/status")
def api_status():
    files = {}
    for f in sorted(OUTPUT_DIR.glob("*.json")) + sorted(OUTPUT_DIR.glob("*.md")):
        if f.name == "checkpoint.json":
            continue
        files[f.name] = {
            "size": f.stat().st_size,
            "mtime": f.stat().st_mtime,
        }
    return jsonify({
        "running": pipeline_state["running"],
        "stage": pipeline_state["stage"],
        "detail": pipeline_state["detail"],
        "files": files,
    })


@app.route("/api/run", methods=["POST"])
def api_run():
    if pipeline_state["running"]:
        return jsonify({"error": "pipeline already running"}), 409

    data = request.get_json()
    topic = data.get("topic", "")
    extra = data.get("extra", "")
    workers = data.get("workers", 2)

    if not topic:
        return jsonify({"error": "topic is required"}), 400

    def run_pipeline():
        pipeline_state["running"] = True
        pipeline_state["stage"] = -1
        pipeline_state["detail"] = "启动中..."
        progress_queue.put({"type": "start", "topic": topic})

        try:
            env = os.environ.copy()
            env["DEEPSEEK_API_KEY"] = "sk-09f508e1d3c14380b23ed34a4206cdbf"

            cmd = [
                sys.executable, "main.py",
                "--topic", topic,
                "--provider", "deepseek",
                "--workers", str(workers),
            ]
            if extra:
                cmd.extend(["--extra", extra])

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(BASE_DIR),
                env=env,
                encoding="utf-8",
                errors="replace",
            )

            for line in process.stdout:
                line = line.rstrip()
                if not line:
                    continue

                progress_queue.put({"type": "log", "line": line})

                if "[1/7]" in line:
                    pipeline_state["stage"] = 0
                    pipeline_state["detail"] = "制定调研计划"
                elif "[2/7]" in line:
                    pipeline_state["stage"] = 1
                    pipeline_state["detail"] = "检索论文"
                elif "[3/7]" in line:
                    pipeline_state["stage"] = 2
                    pipeline_state["detail"] = "筛选相关论文"
                elif "[4/7]" in line:
                    pipeline_state["stage"] = 3
                    pipeline_state["detail"] = "深度分析论文"
                elif "[5/7]" in line:
                    pipeline_state["stage"] = 4
                    pipeline_state["detail"] = "聚类分类"
                elif "[6/7]" in line:
                    pipeline_state["stage"] = 5
                    pipeline_state["detail"] = "撰写综述"
                elif "[7/7]" in line:
                    pipeline_state["stage"] = 6
                    pipeline_state["detail"] = "质量审查"
                elif "完成" in line and "阶段" in line:
                    progress_queue.put({"type": "stage_done", "detail": line})

            process.wait()
            progress_queue.put({"type": "done", "code": process.returncode})

        except Exception as e:
            progress_queue.put({"type": "error", "message": str(e)})
        finally:
            pipeline_state["running"] = False
            pipeline_state["stage"] = -1
            pipeline_state["detail"] = ""

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
    return jsonify({"ok": True})


@app.route("/api/stream")
def api_stream():
    def generate():
        while True:
            try:
                msg = progress_queue.get(timeout=30)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/file/<filename>")
def api_file(filename):
    filepath = OUTPUT_DIR / filename
    if not filepath.exists():
        return jsonify({"error": "not found"}), 404

    if filename.endswith(".json"):
        with open(filepath, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            return jsonify({"content": f.read()})


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(exist_ok=True)
    print("文献综述系统 Web 界面: http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
