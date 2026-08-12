from flask import Flask, jsonify

app = Flask(__name__)


# =========================
# HEALTH ENDPOINT
# =========================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "log-collector"
    }), 200


# =========================
# READINESS ENDPOINT
# =========================

@app.route("/ready", methods=["GET"])
def ready():
    return jsonify({
        "status": "ready",
        "service": "log-collector"
    }), 200


# =========================
# START API SERVER
# =========================

def run_api():
    app.run(
        host="0.0.0.0",
        port=8080,
        debug=False,
        use_reloader=False
    )


if __name__ == "__main__":
    run_api()