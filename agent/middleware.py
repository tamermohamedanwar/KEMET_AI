from flask import Flask, request, jsonify, Response
import os
import requests
import csv
import io

app = Flask(__name__)

GATEWAY_URL = "http://127.0.0.1:8780"
TOKEN = os.getenv("KEMET_AGENT_TOKEN", "")

def call_mcp(method, params=None):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    }

    r = requests.post(
        f"{GATEWAY_URL}/mcp",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        },
        json=payload,
        timeout=60,
    )

    return r.json(), r.status_code


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "Kemet AI Middleware",
        "gateway": GATEWAY_URL
    })


@app.get("/tools")
def tools():
    result, status = call_mcp("tools/list")
    return jsonify(result), status


@app.post("/execute")
def execute():
    data = request.get_json(force=True)

    tool_name = data.get("tool")
    arguments = data.get("arguments", {})

    if not tool_name:
        return jsonify({
            "ok": False,
            "error": "Missing tool"
        }), 400

    result, status = call_mcp(
        "tools/call",
        {
            "name": tool_name,
            "arguments": arguments
        }
    )

    return jsonify(result), status


@app.post("/csv")
def export_csv():
    data = request.get_json(force=True)

    rows = data.get("rows", [])
    filename = data.get("filename", "kemet_export.csv")

    if not isinstance(rows, list) or not rows:
        return jsonify({
            "ok": False,
            "error": "rows must be a non-empty list"
        }), 400

    if not all(isinstance(row, dict) for row in rows):
        return jsonify({
            "ok": False,
            "error": "Each row must be an object"
        }), 400

    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        extrasaction="ignore"
    )

    writer.writeheader()
    writer.writerows(rows)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8790
    )
