import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

BRIDGE_URL = os.getenv(
    "KEMET_BRIDGE_URL",
    "http://127.0.0.1:8770"
)

TOKEN = os.getenv("KEMET_AGENT_TOKEN", "")

HTML = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kemet AI</title>
<style>
body {
    font-family: sans-serif;
    max-width: 900px;
    margin: 30px auto;
    padding: 20px;
    background: #111;
    color: #eee;
}
textarea {
    width: 100%;
    min-height: 120px;
    padding: 12px;
    box-sizing: border-box;
}
button {
    margin-top: 10px;
    padding: 12px 24px;
    cursor: pointer;
}
pre {
    white-space: pre-wrap;
    background: #222;
    padding: 15px;
    overflow-x: auto;
}
</style>
</head>
<body>

<h1>🚀 Kemet AI — Free Bridge</h1>

<p>تنفيذ أدوات Kemet AI مباشرة من الهاتف.</p>

<select id="tool">
<option value="health">health</option>
<option value="test_health">test_health</option>
<option value="compile">compile</option>
<option value="git_status">git_status</option>
<option value="list_files">list_files</option>
<option value="read_file">read_file</option>
<option value="search_code">search_code</option>
</select>

<textarea id="args" placeholder='مثال:
{"path":"README.md"}'></textarea>

<button onclick="runTool()">تنفيذ</button>

<pre id="result">جاهز...</pre>

<script>
async function runTool() {
    const tool = document.getElementById("tool").value;
    const raw = document.getElementById("args").value.trim();

    let arguments = {};

    if (raw) {
        try {
            arguments = JSON.parse(raw);
        } catch (e) {
            document.getElementById("result").textContent =
                "JSON غير صحيح";
            return;
        }
    }

    document.getElementById("result").textContent = "جاري التنفيذ...";

    const response = await fetch("/tool", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            name: tool,
            arguments: arguments
        })
    });

    const data = await response.json();

    document.getElementById("result").textContent =
        JSON.stringify(data, null, 2);
}
</script>

</body>
</html>
"""

@app.get("/")
def index():
    return render_template_string(HTML)


@app.post("/tool")
def tool():
    data = request.get_json(silent=True) or {}

    name = data.get("name")
    arguments = data.get("arguments", {})

    if not name:
        return jsonify({
            "ok": False,
            "error": "tool_required"
        }), 400

    response = requests.post(
        f"{BRIDGE_URL}/mcp",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        },
        timeout=60
    )

    return jsonify(response.json()), response.status_code


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "Kemet AI Free UI"
    })


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8790,
        debug=False
    )
