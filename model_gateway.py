#!/usr/bin/env python3
# OpenAI-compatible multi-model switching gateway for Kaggle.
# Serves llama.cpp's OFFICIAL built-in WebUI by proxying it from the backend,
# while routing /v1/* API calls through the model-switching layer.
# Falls back to a built-in chat page if the backend has no WebUI.
import json, os, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import requests

GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", "8080"))
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8081"))
LLAMA_SERVER = os.environ.get("LLAMA_SERVER", "/kaggle/working/llama-server")
MODEL_CONFIGS = json.loads(os.environ.get("MODEL_CONFIGS", "{}"))
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", next(iter(MODEL_CONFIGS), ""))
LOG_PATH = "/tmp/llama-backend.log"

FALLBACK_UI = '<!DOCTYPE html>\n<html lang="zh">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>Kaggle LLM</title>\n<style>\n:root{--bg:#ffffff;--panel:#fbfbfb;--border:#e8e8e8;--text:#1f1f1f;--muted:#9a9a9a;--bubble:#f4f4f4;--accent:#1a1a1a}\n*{box-sizing:border-box}\nhtml,body{height:100%}\nbody{margin:0;font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;color:var(--text);background:var(--bg);display:flex;font-size:14px}\n#side{width:58px;flex:0 0 58px;background:var(--panel);border-right:1px solid var(--border);display:flex;flex-direction:column;align-items:center;padding:14px 0;gap:8px}\n#side .logo{width:34px;height:34px;border-radius:10px;background:#1a1a1a;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;margin-bottom:8px}\n#side .ico{width:38px;height:38px;border-radius:10px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#666;font-size:19px;user-select:none}\n#side .ico:hover{background:#efefef}\n#side .spacer{flex:1}\n#main{flex:1;display:flex;flex-direction:column;height:100vh;position:relative;min-width:0}\n#wrap{flex:1;overflow-y:auto;display:flex;flex-direction:column;align-items:center}\n#welcome{margin:auto;text-align:center;padding:24px}\n#welcome h1{font-size:30px;font-weight:600;margin:0 0 10px;letter-spacing:-.4px}\n#welcome p{color:var(--muted);margin:0;font-size:15px}\n#msgs{width:min(760px,92%);display:none;flex-direction:column;gap:24px;padding:30px 0 168px}\n.msg{line-height:1.72;white-space:pre-wrap;word-break:break-word}\n.msg .who{font-size:12px;color:var(--muted);margin-bottom:6px}\n.msg.user{align-self:flex-end;max-width:82%;background:var(--bubble);padding:10px 16px;border-radius:18px}\n.msg.user .who{display:none}\n.msg.ai{align-self:flex-start;max-width:100%}\n#composer{position:absolute;left:0;right:0;bottom:0;padding:0 20px 20px;display:flex;justify-content:center;pointer-events:none}\n#box{pointer-events:auto;width:min(760px,92%);background:#fff;border:1px solid #dcdcdc;border-radius:26px;box-shadow:0 6px 26px rgba(0,0,0,.07);padding:14px 14px 9px}\n#box textarea{width:100%;border:0;outline:0;resize:none;font:inherit;font-size:15px;line-height:1.5;max-height:160px;min-height:28px;padding:2px 6px;background:transparent;color:var(--text)}\n#row{display:flex;align-items:center;gap:8px;margin-top:6px}\n.iconbtn{width:32px;height:32px;border-radius:50%;border:1px solid var(--border);background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:18px;color:#555}\n#modelBtn{margin-left:auto;display:flex;align-items:center;gap:7px;border:1px solid var(--border);background:#fafafa;border-radius:18px;padding:6px 12px;cursor:pointer;font-size:13px;color:#333}\n#modelBtn .dot{width:7px;height:7px;border-radius:50%;background:#22a06b}\n#send{width:34px;height:34px;border-radius:50%;border:0;background:var(--accent);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:15px}\n#send:disabled{opacity:.45;cursor:not-allowed}\n#menu{position:absolute;bottom:70px;left:50%;transform:translateX(-50%);background:#fff;border:1px solid var(--border);border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.14);padding:6px;min-width:250px;display:none;z-index:5}\n#menu div{padding:10px 12px;border-radius:9px;cursor:pointer;font-size:14px}\n#menu div:hover{background:#f2f2f2}\n#menu div.on{background:#1a1a1a;color:#fff}\n#hint{font-size:11px;color:#b5b5b5;text-align:center;margin-top:7px}\n</style>\n</head>\n<body>\n<div id="side">\n  <div class="logo" title="Kaggle LLM">K</div>\n  <div class="ico" id="newChat" title="新对话">＋</div>\n  <div class="ico" id="actModel" title="模型">◈</div>\n  <div class="spacer"></div>\n  <div class="ico" title="设置">⚙</div>\n</div>\n<div id="main">\n  <div id="wrap">\n    <div id="welcome">\n      <h1>Hello there</h1>\n      <p>Type a message or upload files to get started</p>\n    </div>\n    <div id="msgs"></div>\n  </div>\n  <div id="menu"></div>\n  <div id="composer">\n    <div id="box">\n      <textarea id="in" rows="1" placeholder="Type a message..."></textarea>\n      <div id="row">\n        <button class="iconbtn" id="plus" title="上传文件（暂未开放）">＋</button>\n        <button id="modelBtn"><span class="dot"></span><span id="modelLabel">加载中…</span><span style="color:#999">▾</span></button>\n        <button id="send" title="发送">➤</button>\n      </div>\n      <div id="hint">点输入框右下角模型标签切换模型，不用改网址</div>\n    </div>\n  </div>\n</div>\n<script>\nconst $=s=>document.querySelector(s);\nlet hist=[], current=\'\', busy=false;\nfunction scroll(){const w=$(\'#wrap\');w.scrollTop=w.scrollHeight}\nfunction setModel(m){\n  current=m;\n  $(\'#modelLabel\').textContent=m.replace(/^.*?:/,\'\');\n  document.querySelectorAll(\'#menu div\').forEach(d=>d.classList.toggle(\'on\',d.dataset.id===m));\n}\nfunction reset(){hist=[];$(\'#msgs\').innerHTML=\'\';$(\'#msgs\').style.display=\'none\';$(\'#welcome\').style.display=\'block\';$(\'#menu\').style.display=\'none\'}\nasync function loadModels(){\n  try{\n    const j=await (await fetch(\'/v1/models\')).json();\n    const menu=$(\'#menu\');menu.innerHTML=\'\';\n    (j.data||[]).forEach(m=>{\n      const d=document.createElement(\'div\');d.dataset.id=m.id;d.textContent=m.id;\n      d.onclick=()=>{setModel(m.id);reset()};\n      menu.appendChild(d);\n    });\n    setModel((j.data[0]||{}).id||\'\');\n  }catch(e){$(\'#modelLabel\').textContent=\'未就绪\'}\n}\nfunction addMsg(who,text){\n  $(\'#welcome\').style.display=\'none\';\n  const box=$(\'#msgs\');box.style.display=\'flex\';\n  const d=document.createElement(\'div\');d.className=\'msg \'+who;\n  const w=document.createElement(\'div\');w.className=\'who\';w.textContent=who===\'user\'?\'You\':current;\n  const t=document.createElement(\'div\');t.textContent=text;\n  d.appendChild(w);d.appendChild(t);box.appendChild(d);scroll();\n  return t;\n}\nasync function send(){\n  if(busy)return;\n  const v=$(\'#in\').value.trim();if(!v)return;\n  $(\'#in\').value=\'\';$(\'#in\').style.height=\'auto\';\n  addMsg(\'user\',v);hist.push({role:\'user\',content:v});\n  const out=addMsg(\'ai\',\'思考中…（首次加载模型可能要 1~2 分钟）\');\n  busy=true;$(\'#send\').disabled=true;\n  try{\n    const r=await fetch(\'/v1/chat/completions\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({model:current,messages:hist})});\n    const j=await r.json();\n    if(j.error)throw new Error(j.error.message);\n    const a=j.choices[0].message.content;\n    out.textContent=a;hist.push({role:\'assistant\',content:a});\n  }catch(e){out.textContent=\'❌ \'+e.message}\n  busy=false;$(\'#send\').disabled=false;scroll();\n}\n$(\'#send\').onclick=send;\n$(\'#in\').onkeydown=e=>{if(e.key===\'Enter\'&&!e.shiftKey){e.preventDefault();send()}};\n$(\'#in\').oninput=()=>{$(\'#in\').style.height=\'auto\';$(\'#in\').style.height=Math.min($(\'#in\').scrollHeight,160)+\'px\'};\nfunction toggleMenu(){const m=$(\'#menu\');m.style.display=m.style.display===\'block\'?\'none\':\'block\'}\n$(\'#modelBtn\').onclick=e=>{e.stopPropagation();toggleMenu()};\n$(\'#actModel\').onclick=e=>{e.stopPropagation();toggleMenu()};\ndocument.addEventListener(\'click\',e=>{if(!e.target.closest(\'#menu\')&&!e.target.closest(\'#modelBtn\')&&!e.target.closest(\'#actModel\')) $(\'#menu\').style.display=\'none\'});\n$(\'#newChat\').onclick=reset;\n$(\'#plus\').onclick=()=>alert(\'文件上传暂未开放，请先输入文字消息。\');\nloadModels();\n</script>\n</body>\n</html>'

_lock = threading.Lock()
_current = None
_proc = None

def log(msg):
    print("[gateway] " + str(msg), flush=True)

def healthy():
    try:
        r = requests.get("http://localhost:%d/health" % BACKEND_PORT, timeout=3)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False

def stop_backend():
    global _proc
    subprocess.run(["pkill", "-f", "llama-server"], capture_output=True)
    if _proc is not None and _proc.poll() is None:
        try:
            _proc.terminate()
            _proc.wait(timeout=20)
        except Exception:
            _proc.kill()
    _proc = None
    time.sleep(2)

def start_backend(alias):
    global _proc, _current
    cfg = MODEL_CONFIGS[alias]
    cmd = [
        LLAMA_SERVER,
        "--model", cfg["model"],
        "--host", "0.0.0.0",
        "--port", str(BACKEND_PORT),
        "--alias", alias,
        "--n-gpu-layers", str(cfg.get("ngl", 999)),
        "--ctx-size", str(cfg.get("ctx", 16384)),
        "--temp", str(cfg.get("temp", 0.7)),
        "--top-p", str(cfg.get("top_p", 0.8)),
        "--top-k", str(cfg.get("top_k", 20)),
        "--min-p", str(cfg.get("min_p", 0.0)),
        "--presence-penalty", str(cfg.get("presence", 1.5)),
        "--log-file", LOG_PATH,
    ]
    if cfg.get("mmproj"):
        cmd += ["--mmproj", cfg["mmproj"]]
    for extra in cfg.get("extra_args", []):
        cmd += [extra]
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = "/kaggle/working:" + env.get("LD_LIBRARY_PATH", "")
    log("starting backend: " + alias)
    with open("/tmp/llama-backend-stdout.log", "w") as out:
        _proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, env=env)
    deadline = time.time() + 900
    while time.time() < deadline:
        if healthy():
            _current = alias
            log("backend ready: " + alias)
            return True
        if _proc.poll() is not None:
            log("backend exited early; check /tmp/llama-backend-stdout.log")
            return False
        time.sleep(3)
    log("backend load timeout")
    return False

def ensure_model(alias):
    global _current
    with _lock:
        if alias not in MODEL_CONFIGS:
            return False
        if _current == alias and healthy():
            return True
        stop_backend()
        return start_backend(alias)

def official_webui_available():
    """True when llama-server serves its built-in WebUI at /."""
    try:
        r = requests.get("http://localhost:%d/" % BACKEND_PORT, timeout=8)
        t = r.text
        return r.status_code == 200 and (("<!DOCTYPE html" in t) or ("/assets/" in t) or ("llama" in t.lower()))
    except Exception:
        return False

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html, status=200):
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        p = self.path
        if p == "/health":
            self._send_json({"status": "ok", "current_model": _current,
                             "available": list(MODEL_CONFIGS.keys())})
            return
        if p.startswith("/v1/models"):
            data = [{"id": a, "object": "model", "owned_by": "kaggle", "created": 0,
                     "status": {"value": "loaded", "args": []}}
                    for a in MODEL_CONFIGS]
            self._send_json({"object": "list", "data": data})
            return
        if p == "/models/sse":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                for _a in MODEL_CONFIGS:
                    _ev = {"model": _a, "event": "model_status",
                           "data": {"value": "loaded", "args": []}}
                    self.wfile.write(("data: " + json.dumps(_ev) + "\n\n").encode())
                self.wfile.flush()
                for _ in range(600):
                    time.sleep(1)
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except Exception:
                pass
            return
        if p == "/v1/model":
            self._send_json({"current_model": _current})
            return
        # Everything else: official llama.cpp WebUI (/, /assets/*, /props, ...)
        self._serve_webui("GET")

    def do_POST(self):
        p = self.path
        if p == "/models/load":
            self._router_load()
            return
        if p == "/models/unload":
            self._send_json({"success": True})
            return
        if p.startswith("/v1/") or p.startswith("/completion"):
            self._forward_api("POST")
        else:
            self._serve_webui("POST")

    def _router_load(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        wanted = None
        if raw:
            try:
                wanted = json.loads(raw).get("model")
            except Exception:
                pass
        if wanted not in MODEL_CONFIGS:
            self._send_json({"error": {"message": "unknown model: " + str(wanted),
                                       "type": "invalid_request_error"}}, 404)
            return
        if ensure_model(wanted):
            self._send_json({"success": True, "model": wanted})
        else:
            self._send_json({"error": {"message": "failed to load " + wanted,
                                       "type": "server_error"}}, 500)

    def _serve_webui(self, method):
        alias = _current if _current in MODEL_CONFIGS else DEFAULT_MODEL
        if not ensure_model(alias):
            self._send_json({"error": {"message": "Backend failed to load " + alias,
                                       "type": "server_error"}}, 503)
            return
        if method == "GET" and self.path in ("/", "/index.html"):
            if official_webui_available():
                log("serving OFFICIAL llama.cpp WebUI")
                self._raw_proxy("GET")
            else:
                log("official WebUI not found; serving fallback chat page")
                self._send_html(FALLBACK_UI)
            return
        self._raw_proxy(method)

    def _raw_proxy(self, method):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        url = "http://localhost:%d%s" % (BACKEND_PORT, self.path)
        fwd = {k: v for k, v in self.headers.items()
               if k.lower() not in ("host", "content-length", "transfer-encoding", "connection")}
        try:
            r = requests.request(method, url, data=body if body else None,
                                 headers=fwd, stream=True, timeout=(10, 3600))
        except Exception as e:
            self._send_json({"error": {"message": str(e), "type": "server_error"}}, 502)
            return
        is_stream = "text/event-stream" in r.headers.get("content-type", "")
        self.send_response(r.status_code)
        for k, v in r.headers.items():
            if k.lower() in ("content-length", "transfer-encoding", "connection", "content-encoding"):
                continue
            self.send_header(k, v)
        if is_stream:
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        self.wfile.write(("%X\r\n" % len(chunk)).encode() + chunk + b"\r\n")
                        self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except Exception:
                pass
        else:
            payload = r.content
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def _forward_api(self, method):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        wanted = None
        if body:
            try:
                wanted = json.loads(body).get("model")
            except Exception:
                pass
        alias = wanted if wanted in MODEL_CONFIGS else (DEFAULT_MODEL if wanted is None else None)
        if alias is None:
            self._send_json({"error": {"message": "Unknown model: " + str(wanted),
                                       "type": "invalid_request_error"}}, 400)
            return
        if not ensure_model(alias):
            self._send_json({"error": {"message": "Failed to load model " + alias,
                                       "type": "server_error"}}, 500)
            return
        url = "http://localhost:%d%s" % (BACKEND_PORT, self.path)
        fwd = {k: v for k, v in self.headers.items()
               if k.lower() not in ("host", "content-length", "transfer-encoding", "connection")}
        try:
            r = requests.request(method, url, data=body if body else None,
                                 headers=fwd, stream=True, timeout=(10, 3600))
        except Exception as e:
            self._send_json({"error": {"message": str(e), "type": "server_error"}}, 502)
            return
        is_stream = "text/event-stream" in r.headers.get("content-type", "")
        self.send_response(r.status_code)
        for k, v in r.headers.items():
            if k.lower() in ("content-length", "transfer-encoding", "connection", "content-encoding"):
                continue
            self.send_header(k, v)
        if is_stream:
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        self.wfile.write(("%X\r\n" % len(chunk)).encode() + chunk + b"\r\n")
                        self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except Exception:
                pass
        else:
            payload = r.content
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

if __name__ == "__main__":
    log("available models: " + ", ".join(MODEL_CONFIGS.keys()))
    log("default model: " + DEFAULT_MODEL)
    srv = ThreadingHTTPServer(("0.0.0.0", GATEWAY_PORT), Handler)
    log("gateway listening on port " + str(GATEWAY_PORT))
    threading.Thread(target=ensure_model, args=(DEFAULT_MODEL,), daemon=True).start()
    srv.serve_forever()
