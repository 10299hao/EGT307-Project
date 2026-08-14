import os
import tempfile

from flask import Flask, jsonify, request

from ingest import process_upload

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "log-collector"}), 200


@app.route("/ready", methods=["GET"])
def ready():
    return jsonify({"status": "ready", "service": "log-collector"}), 200


@app.route("/ingest", methods=["POST"])
def ingest():
    if "file" not in request.files:
        return jsonify({"error": "No 'file' field in upload"}), 400

    uploaded = request.files["file"]
    labels_uploaded = request.files.get("labels_file")

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "upload.csv")
        uploaded.save(csv_path)

        labels_path = None
        if labels_uploaded:
            labels_path = os.path.join(tmpdir, "labels.csv")
            labels_uploaded.save(labels_path)

        summary = process_upload(csv_path, labels_path)

    status_code = 200 if not summary.get("error") else 422
    return jsonify(summary), status_code


def run_api():
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_api()