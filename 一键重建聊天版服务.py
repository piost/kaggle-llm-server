# -*- coding: utf-8 -*-
# ============================================================
# 一键重建「网页聊天窗口」服务
#
# 为什么需要它：
#   Cell 7 是 while True 保活循环，霸占着 Kaggle 内核。
#   Kaggle 内核一次只能跑一个单元格，所以你新加的单元格
#   点了运行只会排队，永远轮不到 —— 这就是"点了没反应"。
#
# 用法（3 步）：
#   1) 点工具栏的 ■ (Interrupt Kernel) 停掉当前服务（正常，URL 会变）
#   2) 把本文件全部内容粘贴到那个新单元格，运行
#   3) 打印出新 URL 后，浏览器打开它（不要加 /v1）就是聊天窗口
#
# 注意：不要在这个脚本之后再 Run All！
#   旧版 Cell 10 会把聊天界面覆盖掉。这个脚本自己已经把
#   网关 + 隧道 + 保活全部拉起来了，不需要 Run All。
# ============================================================
import os, json, subprocess, time, re, datetime, requests

GP = '/kaggle/working/model_gateway.py'

# ---- 1) 读取配置（Interrupt 不清空内核变量，优先用现成的） ----
def _cfg(name, default=None):
    if name in globals():
        return globals()[name]
    return os.environ.get(name, default)

_PORT    = int(_cfg('PORT', os.environ.get('GATEWAY_PORT', '8080')))
_BACKEND = int(_cfg('BACKEND_PORT', os.environ.get('BACKEND_PORT', '8081')))
_LLAMA   = str(_cfg('LLAMA_SERVER', os.environ.get('LLAMA_SERVER', '/kaggle/working/llama-server')))
_CFG     = _cfg('MODEL_CONFIGS', None) or json.loads(os.environ.get('MODEL_CONFIGS', '{}'))
_DEFAULT = _cfg('DEFAULT_MODEL', None) or os.environ.get('DEFAULT_MODEL') or next(iter(_CFG), '')
assert _CFG, '读不到模型配置，请确认之前 Run All 成功过（内核变量被清了就 Restart 后重跑 Cell 2）'

# ---- 2) 给网关注入聊天界面（幂等，重复运行不会出错） ----
WEB_UI = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kaggle LLM</title>
<style>
:root{--bg:#ffffff;--panel:#fbfbfb;--border:#e8e8e8;--text:#1f1f1f;--muted:#9a9a9a;--bubble:#f4f4f4;--accent:#1a1a1a}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;color:var(--text);background:var(--bg);display:flex;font-size:14px}
#side{width:58px;flex:0 0 58px;background:var(--panel);border-right:1px solid var(--border);display:flex;flex-direction:column;align-items:center;padding:14px 0;gap:8px}
#side .logo{width:34px;height:34px;border-radius:10px;background:#1a1a1a;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;margin-bottom:8px}
#side .ico{width:38px;height:38px;border-radius:10px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#666;font-size:19px;user-select:none}
#side .ico:hover{background:#efefef}
#side .spacer{flex:1}
#main{flex:1;display:flex;flex-direction:column;height:100vh;position:relative;min-width:0}
#wrap{flex:1;overflow-y:auto;display:flex;flex-direction:column;align-items:center}
#welcome{margin:auto;text-align:center;padding:24px}
#welcome h1{font-size:30px;font-weight:600;margin:0 0 10px;letter-spacing:-.4px}
#welcome p{color:var(--muted);margin:0;font-size:15px}
#msgs{width:min(760px,92%);display:none;flex-direction:column;gap:24px;padding:30px 0 168px}
.msg{line-height:1.72;white-space:pre-wrap;word-break:break-word}
.msg .who{font-size:12px;color:var(--muted);margin-bottom:6px}
.msg.user{align-self:flex-end;max-width:82%;background:var(--bubble);padding:10px 16px;border-radius:18px}
.msg.user .who{display:none}
.msg.ai{align-self:flex-start;max-width:100%}
#composer{position:absolute;left:0;right:0;bottom:0;padding:0 20px 20px;display:flex;justify-content:center;pointer-events:none}
#box{pointer-events:auto;width:min(760px,92%);background:#fff;border:1px solid #dcdcdc;border-radius:26px;box-shadow:0 6px 26px rgba(0,0,0,.07);padding:14px 14px 9px}
#box textarea{width:100%;border:0;outline:0;resize:none;font:inherit;font-size:15px;line-height:1.5;max-height:160px;min-height:28px;padding:2px 6px;background:transparent;color:var(--text)}
#row{display:flex;align-items:center;gap:8px;margin-top:6px}
.iconbtn{width:32px;height:32px;border-radius:50%;border:1px solid var(--border);background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:18px;color:#555}
#modelBtn{margin-left:auto;display:flex;align-items:center;gap:7px;border:1px solid var(--border);background:#fafafa;border-radius:18px;padding:6px 12px;cursor:pointer;font-size:13px;color:#333}
#modelBtn .dot{width:7px;height:7px;border-radius:50%;background:#22a06b}
#send{width:34px;height:34px;border-radius:50%;border:0;background:var(--accent);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:15px}
#send:disabled{opacity:.45;cursor:not-allowed}
#menu{position:absolute;bottom:70px;left:50%;transform:translateX(-50%);background:#fff;border:1px solid var(--border);border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.14);padding:6px;min-width:250px;display:none;z-index:5}
#menu div{padding:10px 12px;border-radius:9px;cursor:pointer;font-size:14px}
#menu div:hover{background:#f2f2f2}
#menu div.on{background:#1a1a1a;color:#fff}
#hint{font-size:11px;color:#b5b5b5;text-align:center;margin-top:7px}
</style>
</head>
<body>
<div id="side">
  <div class="logo" title="Kaggle LLM">K</div>
  <div class="ico" id="newChat" title="新对话">＋</div>
  <div class="ico" id="actModel" title="模型">◈</div>
  <div class="spacer"></div>
  <div class="ico" title="设置">⚙</div>
</div>
<div id="main">
  <div id="wrap">
    <div id="welcome">
      <h1>Hello there</h1>
      <p>Type a message or upload files to get started</p>
    </div>
    <div id="msgs"></div>
  </div>
  <div id="menu"></div>
  <div id="composer">
    <div id="box">
      <textarea id="in" rows="1" placeholder="Type a message..."></textarea>
      <div id="row">
        <button class="iconbtn" id="plus" title="上传文件（暂未开放）">＋</button>
        <button id="modelBtn"><span class="dot"></span><span id="modelLabel">加载中…</span><span style="color:#999">▾</span></button>
        <button id="send" title="发送">➤</button>
      </div>
      <div id="hint">点输入框右下角模型标签切换模型，不用改网址</div>
    </div>
  </div>
</div>
<script>
const $=s=>document.querySelector(s);
let hist=[], current='', busy=false;
function scroll(){const w=$('#wrap');w.scrollTop=w.scrollHeight}
function setModel(m){
  current=m;
  $('#modelLabel').textContent=m.replace(/^.*?:/,'');
  document.querySelectorAll('#menu div').forEach(d=>d.classList.toggle('on',d.dataset.id===m));
}
function reset(){hist=[];$('#msgs').innerHTML='';$('#msgs').style.display='none';$('#welcome').style.display='block';$('#menu').style.display='none'}
async function loadModels(){
  try{
    const j=await (await fetch('/v1/models')).json();
    const menu=$('#menu');menu.innerHTML='';
    (j.data||[]).forEach(m=>{
      const d=document.createElement('div');d.dataset.id=m.id;d.textContent=m.id;
      d.onclick=()=>{setModel(m.id);reset()};
      menu.appendChild(d);
    });
    setModel((j.data[0]||{}).id||'');
  }catch(e){$('#modelLabel').textContent='未就绪'}
}
function addMsg(who,text){
  $('#welcome').style.display='none';
  const box=$('#msgs');box.style.display='flex';
  const d=document.createElement('div');d.className='msg '+who;
  const w=document.createElement('div');w.className='who';w.textContent=who==='user'?'You':current;
  const t=document.createElement('div');t.textContent=text;
  d.appendChild(w);d.appendChild(t);box.appendChild(d);scroll();
  return t;
}
async function send(){
  if(busy)return;
  const v=$('#in').value.trim();if(!v)return;
  $('#in').value='';$('#in').style.height='auto';
  addMsg('user',v);hist.push({role:'user',content:v});
  const out=addMsg('ai','思考中…（首次加载模型可能要 1~2 分钟）');
  busy=true;$('#send').disabled=true;
  try{
    const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:current,messages:hist})});
    const j=await r.json();
    if(j.error)throw new Error(j.error.message);
    const a=j.choices[0].message.content;
    out.textContent=a;hist.push({role:'assistant',content:a});
  }catch(e){out.textContent='❌ '+e.message}
  busy=false;$('#send').disabled=false;scroll();
}
$('#send').onclick=send;
$('#in').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}};
$('#in').oninput=()=>{$('#in').style.height='auto';$('#in').style.height=Math.min($('#in').scrollHeight,160)+'px'};
function toggleMenu(){const m=$('#menu');m.style.display=m.style.display==='block'?'none':'block'}
$('#modelBtn').onclick=e=>{e.stopPropagation();toggleMenu()};
$('#actModel').onclick=e=>{e.stopPropagation();toggleMenu()};
document.addEventListener('click',e=>{if(!e.target.closest('#menu')&&!e.target.closest('#modelBtn')&&!e.target.closest('#actModel')) $('#menu').style.display='none'});
$('#newChat').onclick=reset;
$('#plus').onclick=()=>alert('文件上传暂未开放，请先输入文字消息。');
loadModels();
</script>
</body>
</html>"""

s = open(GP, encoding='utf-8').read()
if 'WEB_UI = ' in s:
    print('聊天界面已在网关里，跳过注入')
else:
    anchor = 'def log(msg):'
    assert anchor in s, '网关版本不匹配，请重新导入最新版 2_run_server.ipynb'
    s = s.replace(anchor, 'WEB_UI = ' + repr(WEB_UI) + '\n\n' + anchor, 1)
    old = '''        if self.path in ("/health", "/"):
            self._send_json({"status": "ok", "current_model": _current,
                             "available": list(MODEL_CONFIGS.keys())})
            return
'''
    new = '''        if self.path == "/health":
            self._send_json({"status": "ok", "current_model": _current,
                             "available": list(MODEL_CONFIGS.keys())})
            return
        if self.path in ("/", "/index.html"):
            _data = WEB_UI.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(_data)))
            self.end_headers()
            self.wfile.write(_data)
            return
'''
    assert old in s, '网关路由不匹配，请重新导入最新版 2_run_server.ipynb'
    s = s.replace(old, new, 1)
    open(GP, 'w', encoding='utf-8').write(s)
    print('OK 聊天界面已注入网关')

# ---- 3) 环境变量（网关子进程要用） ----
os.environ.update(
    MODEL_CONFIGS=json.dumps(_CFG, ensure_ascii=False),
    DEFAULT_MODEL=_DEFAULT,
    GATEWAY_PORT=str(_PORT),
    BACKEND_PORT=str(_BACKEND),
    LLAMA_SERVER=_LLAMA,
)

# ---- 4) 清理旧进程 ----
subprocess.run(['pkill', '-f', 'model_gateway.py'], capture_output=True)
subprocess.run(['pkill', '-f', 'cloudflared'], capture_output=True)
subprocess.run(['pkill', '-f', 'llama-server'], capture_output=True)
time.sleep(2)

# ---- 5) 重启网关 ----
gateway_proc = subprocess.Popen(
    ['python', GP], stdout=open('/tmp/gateway.log', 'w'),
    stderr=subprocess.STDOUT, env={**os.environ}, start_new_session=True)
time.sleep(4)
try:
    print('网关状态:', requests.get(f'http://localhost:{_PORT}/health', timeout=5).json())
except Exception as e:
    print('网关启动中，稍后健康检查会确认:', e)

# ---- 6) 重启 Cloudflare 隧道，拿新 URL ----
tunnel_log = '/tmp/cloudflare.log'
with open(tunnel_log, 'w') as log:
    tunnel_proc = subprocess.Popen(
        ['cloudflared', 'tunnel', '--url', f'http://localhost:{_PORT}'],
        stdout=log, stderr=log, start_new_session=True)

url = None
for _ in range(30):
    time.sleep(2)
    try:
        m = re.search(r'https://[\w-]+\.trycloudflare\.com', open(tunnel_log).read())
        if m:
            url = m.group(0)
            break
    except Exception:
        pass

if not url:
    print('隧道启动失败，最后日志：')
    print(open(tunnel_log).read()[-1000:])
    raise RuntimeError('Cloudflare tunnel failed')

print()
print('=' * 62)
print('  聊天窗口地址（浏览器打开这个，不要加 /v1）：')
print(f'  {url}')
print(f'  OpenAI API: {url}/v1')
print('=' * 62)

# ---- 7) 保活循环 ----
print('\n服务运行中；这个单元格会一直转圈是正常的，别停。')
_t0 = datetime.datetime.now()
try:
    while True:
        time.sleep(300)
        try:
            _info = requests.get(f'http://localhost:{_PORT}/health', timeout=5).json()
            _st = 'OK model=' + str(_info.get('current_model'))
        except Exception:
            _st = 'UNREACHABLE'
        h, rem = divmod(int((datetime.datetime.now() - _t0).total_seconds()), 3600)
        print(f'[{datetime.datetime.now():%H:%M:%S}] uptime {h}h {rem//60:02d}m | {_st}')
except KeyboardInterrupt:
    print('已停止')
