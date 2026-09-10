from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

BRIDGE_URL = "http://127.0.0.1:8770"
TOKEN = os.getenv("KEMET_AGENT_TOKEN", "")

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "Kemet AI Free Gateway"
    })

@app.post("/mcp")
def mcp():
    auth = request.headers.get("Authorization", "")

    if not TOKEN or auth != f"Bearer {TOKEN}":
        return jsonify({"error": "Unauthorized"}), 401

    r = requests.post(
        f"{BRIDGE_URL}/mcp",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        },
        json=request.get_json(force=True),
        timeout=60,
    )

    return (r.text, r.status_code, {
        "Content-Type": "application/json"
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8780)
