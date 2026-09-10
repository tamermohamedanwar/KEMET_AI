import os
import json
import requests
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv(".env", override=True)
load_dotenv(".env.local", override=True)
load_dotenv(".env.agent", override=True)

app = Flask(__name__)

PROJECT = Path(os.path.expanduser("~/products/Kemet_AI")).resolve()
BRIDGE_URL = os.getenv("KEMET_BRIDGE_URL", "http://127.0.0.1:8770")
TOKEN = os.getenv("KEMET_AGENT_TOKEN", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")

MODEL = os.getenv("KEMET_AI_MODEL", "openrouter/free")

MAX_TOOL_ROUNDS = 20
MAX_EXECUTION_ERRORS = 3


def bridge_call(name, arguments=None):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments or {}
        }
    }

    response = requests.post(
        f"{BRIDGE_URL}/mcp",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=120
    )

    response.raise_for_status()
    return response.json()


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories inside the Kemet AI project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project-relative directory path."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file inside the Kemet AI project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project-relative file path."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search source code inside the Kemet AI project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string"
                    },
                    "path": {
                        "type": "string"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or replace a project file. The server automatically creates a backup.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string"
                    },
                    "content": {
                        "type": "string"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compile",
            "description": "Compile the Python application.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "test_health",
            "description": "Check the Kemet AI application health endpoint.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Get the current git status.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


def execute_tool(name, arguments):
    return bridge_call(name, arguments)


SYSTEM_PROMPT = """
You are Kemet AI Autonomous Coding Agent.

You operate the Kemet AI project through approved tools.

The project root is Kemet_AI.

Your job is to understand the user's request, inspect the existing project, plan the work, modify project files, test the changes, fix errors, and report the final result.

Rules:

1. Never access files outside the project.
2. Never request or expose secrets.
3. Never read .env, .env.local, .env.agent, credentials, tokens, private keys, or similar secret files.
4. Before modifying existing code, inspect the relevant files.
5. Prefer small safe changes.
6. When creating a feature, inspect the existing architecture first.
7. Use write_file for actual implementation.
8. After Python changes, run compile.
9. When appropriate, run application health checks.
10. If a test or compile fails, inspect the error, fix the code, and retry.
11. Do not merely describe code that could be written. Actually write it when the user asks for implementation.
12. Do not claim success unless the implementation or verification was actually performed.
13. Keep the user informed with a concise progress-oriented final response.
14. Do not modify secret files.
15. Do not execute arbitrary shell commands. Use only the approved tools.

When the request is large, break it into safe implementation steps and execute them sequentially.
"""


def ask_ai(message, history):
    execution_log = []

    if not OPENROUTER_KEY:
        return {
            "ok": False,
            "answer": "AI provider is not configured."
        }

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    for item in history[-12:]:
        messages.append(item)

    messages.append({
        "role": "user",
        "content": message
    })

    for _ in range(MAX_TOOL_ROUNDS):
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://127.0.0.1:8780",
                "X-Title": "Kemet AI Autonomous Agent"
            },
            json={
                "model": MODEL,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto"
            },
            timeout=180
        )

        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        assistant_message = choice["message"]

        messages.append(assistant_message)

        tool_calls = assistant_message.get("tool_calls") or []

        if not tool_calls:
            return {
                "ok": True,
                "answer": assistant_message.get("content") or "Completed.",
                "execution_log": execution_log,
                "messages": messages
            }

        for call in tool_calls:
            function = call["function"]
            name = function["name"]

            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}

            if name in {
                "read_file",
                "list_files",
                "search_code",
                "write_file",
                "compile",
                "test_health",
                "git_status"
            }:
                try:
                    result = execute_tool(name, arguments)
                    execution_log.append({
                        "tool": name,
                        "arguments": arguments,
                        "result": result
                    })
                except Exception as exc:
                    result = {
                        "ok": False,
                        "error": str(exc)
                    }
            else:
                result = {
                    "ok": False,
                    "error": "tool_not_allowed"
                }

            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(
                    result,
                    ensure_ascii=False
                )
            })

    return {
        "ok": False,
        "answer": "The agent reached the maximum planning and execution rounds.",
        "execution_log": execution_log
    }


HTML = """
<!doctype html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kemet AI Autonomous Agent</title>
<style>
*{box-sizing:border-box}
body{
margin:0;
background:#08110d;
color:#ecfdf5;
font-family:Arial,sans-serif
}
.container{
max-width:900px;
margin:auto;
min-height:100vh;
display:flex;
flex-direction:column
}
.header{
padding:20px;
background:#0d1b14;
border-bottom:1px solid #244236
}
.header h1{margin:0;font-size:23px}
.status{
margin-top:7px;
color:#6ee7a1;
font-size:13px
}
.chat{
flex:1;
padding:18px;
overflow-y:auto
}
.message{
padding:15px;
margin-bottom:12px;
border-radius:15px;
white-space:pre-wrap;
line-height:1.65
}
.user{background:#174b35}
.assistant{background:#14221b}
.input{
padding:15px;
background:#0d1b14;
border-top:1px solid #244236
}
textarea{
width:100%;
min-height:110px;
resize:vertical;
background:#07100c;
color:#fff;
border:1px solid #315746;
border-radius:14px;
padding:15px;
font-size:17px;
outline:none
}
textarea:focus{border-color:#55b77f}
button{
width:100%;
margin-top:10px;
padding:14px;
border:0;
border-radius:13px;
background:#16a34a;
color:white;
font-size:17px;
font-weight:bold
}
button:disabled{opacity:.5}
.small{
margin-top:10px;
font-size:12px;
color:#91a99c
}
</style>
</head>
<body>
<div class="container">

<div class="header">
<h1>Kemet AI Autonomous Agent</h1>
<div class="status">Connected to local project agent</div>
</div>

<div id="chat" class="chat">
<div class="message assistant">
Ready. Describe what you want me to build, change, test, or fix.
</div>
</div>

<div class="input">
<textarea id="message" placeholder="Describe what you want the agent to build or change..."></textarea>
<button id="send">Execute</button>
<div class="small">
Changes are restricted to the Kemet AI project and protected files are blocked.
</div>
</div>

</div>

<script>
const chat=document.getElementById("chat");
const message=document.getElementById("message");
const send=document.getElementById("send");

function add(cls,text){
const d=document.createElement("div");
d.className="message "+cls;
d.textContent=text;
chat.appendChild(d);
chat.scrollTop=chat.scrollHeight;
}

send.onclick=async()=>{
const text=message.value.trim();
if(!text)return;

add("user",text);
message.value="";
send.disabled=true;
send.textContent="Working...";

try{
const r=await fetch("/chat",{
method:"POST",
headers:{
"Content-Type":"application/json"
},
body:JSON.stringify({message:text})
});

const data=await r.json();

add(
"assistant",
data.answer || JSON.stringify(data,null,2)
);

}catch(e){
add("assistant","Connection error: "+e);
}

send.disabled=false;
send.textContent="Execute";
};

message.addEventListener("keydown",e=>{
if(e.key==="Enter" && !e.shiftKey){
e.preventDefault();
send.click();
}
});
</script>

</body>
</html>
"""


@app.get("/")
def home():
    return render_template_string(HTML)


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "Kemet AI Autonomous Agent V4",
        "project": str(PROJECT),
        "bridge": BRIDGE_URL,
        "model": MODEL,
        "ai_configured": bool(OPENROUTER_KEY)
    })


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({
            "ok": False,
            "answer": "Message is required."
        }), 400

    try:
        result = ask_ai(message, [])
        return jsonify(result)
    except Exception as exc:
        return jsonify({
            "ok": False,
            "answer": f"Agent error: {exc}"
        }), 500


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8780,
        debug=False
    )
