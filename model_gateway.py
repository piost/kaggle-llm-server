#!/usr/bin/env python3
# OpenAI-compatible multi-model switching gateway for Kaggle.
# Clients always talk to port 8080. The gateway loads the requested model into
# a single llama-server backend (port 8081), so each model gets full VRAM.
import json, os, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import requests

GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", "8080"))
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8081"))
LLAMA_SERVER = os.environ.get("LLAMA_SERVER", "/kaggle/working/llama-server")
MODEL_CONFIGS = json.loads(os.environ.get("MODEL_CONFIGS", "{}"))
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", next(iter(MODEL_CONFIGS), ""))
LOG_PATH = "/tmp/llama-backend.log"

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

    def do_GET(self):
        if self.path in ("/health", "/"):
            self._send_json({"status": "ok", "current_model": _current,
                             "available": list(MODEL_CONFIGS.keys())})
            return
        if self.path.startswith("/v1/models"):
            data = [{"id": a, "object": "model", "owned_by": "kaggle", "created": 0}
                    for a in MODEL_CONFIGS]
            self._send_json({"object": "list", "data": data})
            return
        if self.path.startswith("/v1/model"):
            self._send_json({"current_model": _current})
            return
        self._forward("GET")

    def do_POST(self):
        self._forward("POST")

    def _forward(self, method):
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
        fwd_headers = {k: v for k, v in self.headers.items()
                       if k.lower() not in ("host", "content-length", "transfer-encoding", "connection")}
        try:
            r = requests.request(method, url, data=body if body else None,
                                 headers=fwd_headers, stream=True, timeout=(10, 3600))
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
    srv.serve_forever()
