import os
import shutil
import tempfile
import threading
import uuid

from flask import Flask, jsonify, request

from ingest import process_upload

app = Flask(__name__)

jobs = {}
jobs_lock = threading.Lock()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "log-collector"}), 200


@app.route("/ready", methods=["GET"])
def ready():
    return jsonify({"status": "ready", "service": "log-collector"}), 200


def _run_ingest_job(job_id, csv_path, labels_path, tmpdir):
    with jobs_lock:
        jobs[job_id]["status"] = "processing"
    try:
        summary = process_upload(csv_path, labels_path)
        with jobs_lock:
            jobs[job_id]["status"] = "failed" if summary.get("error") else "completed"
            jobs[job_id]["summary"] = summary
    except Exception as e:
        with jobs_lock:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["summary"] = {"error": str(e)}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@app.route("/ingest", methods=["POST"])
def ingest():
    if "file" not in request.files:
        return jsonify({"error": "No 'file' field in upload"}), 400

    uploaded = request.files["file"]
    labels_uploaded = request.files.get("labels_file")

    tmpdir = tempfile.mkdtemp()
    csv_path = os.path.join(tmpdir, "upload.csv")
    uploaded.save(csv_path)

    labels_path = None
    if labels_uploaded:
        labels_path = os.path.join(tmpdir, "labels.csv")
        labels_uploaded.save(labels_path)

    job_id = str(uuid.uuid4())
    with jobs_lock:
        jobs[job_id] = {"status": "queued", "summary": None}

    thread = threading.Thread(
        target=_run_ingest_job,
        args=(job_id, csv_path, labels_path, tmpdir),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id, "status": "queued"}), 202


@app.route("/ingest/status/<job_id>", methods=["GET"])
def ingest_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Unknown job_id"}), 404
    return jsonify({"job_id": job_id, **job}), 200


def run_api():
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    run_api()