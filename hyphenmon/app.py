import random
import time

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/metrics")
def metrics():
    return jsonify(
        {
            "timestamp": int(time.time()),
            "response_time_ms": random.randint(100, 500),
            "error_rate": round(random.uniform(0.0, 1.0), 2),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
