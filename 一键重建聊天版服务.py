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
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:#f7f7f8;color:#111}
#top{padding:10px 16px;border-bottom:1px solid #e5e5e7;background:#fff;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:2}
#top b{font-size:16px}
select{padding:6px 10px;font-size:14px;border:1px solid #d0d0d4;border-radius:8px;background:#fff}
#stat{font-size:12px;color:#888;margin-left:auto}
#chat{max-width:760px;margin:18px auto 90px;padding:0 16px}
.msg{margin:14px 0;line-height:1.7;white-space:pre-wrap;word-break:break-word}
.msg u{display:block;font-size:12px;color:#999;text-decoration:none;margin-bottom:4px}
.msg.user{text-align:right}
.msg.user>div{display:inline-block;background:#3b82f6;color:#fff;padding:10px 14px;border-radius:14px;text-align:left}
.msg.ai>div{display:inline-block;background:#fff;border:1px solid #e5e5e7;padding:10px 14px;border-radius:14px}
#bar{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid #e5e5e7;padding:12px 16px;display:flex;gap:10px;justify-content:center}
#in{width:min(680px,88vw);padding:11px 14px;border:1px solid #d0d0d4;border-radius:10px;font-size:14px;font-family:inherit;outline:none}
#in:focus{border-color:#3b82f6}
button{padding:0 20px;border:0;background:#3b82f6;color:#fff;border-radius:10px;cursor:pointer;font-size:14px}
button:disabled{background:#9dbcf5;cursor:not-allowed}
#hint{font-size:12px;color:#999;text-align:center;margin-top:8px}
</style>
</head>
<body>
<div id="top"><b>🤖 Kaggle LLM</b><select id="model"></select><span id="stat"></span></div>
<div id="chat"><div class="msg ai"><u>系统</u><div>选择模型后开始对话。首次切换模型需等待加载 10 秒~2 分钟。</div></div></div>
<div id="bar">
  <input id="in" placeholder="输入消息，按 Enter 发送">
  <button id="go">发送</button>
</div>
<div id="hint">模型切换不用改网址，用上面的下拉框即可</div>
<script>
const $=s=>document.querySelector(s);
let hist=[];
async function loadModels(){
  try{
    const j=await (await fetch('/v1/models')).json();
    const s=$('#model');s.innerHTML='';
    (j.data||[]).forEach(m=>{const o=document.createElement('option');o.value=m.id;o.textContent=m.id;s.appendChild(o)});
    $('#stat').textContent='● 在线';
  }catch(e){$('#stat').textContent='○ 未就绪'}
}
function add(who,text){
  const d=document.createElement('div');d.className='msg '+who;
  const u=document.createElement('u');u.textContent=who==='user'?'你':$('#model').value;
  const box=document.createElement('div');box.textContent=text;
  d.appendChild(u);d.appendChild(box);$('#chat').appendChild(d);
  window.scrollTo(0,document.body.scrollHeight);
  return box;
}
async function send(){
  const t=$('#in').value.trim();if(!t)return;
  $('#in').value='';add('user',t);hist.push({role:'user',content:t});
  const out=add('ai','思考中…（首次加载模型可能要 1-2 分钟）');
  $('#go').disabled=true;
  try{
    const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({model:$('#model').value,messages:hist})});
    const j=await r.json();
    if(j.error)throw new Error(j.error.message);
    const a=j.choices[0].message.content;
    out.textContent=a;hist.push({role:'assistant',content:a});
  }catch(e){out.textContent='❌ '+e.message}
  $('#go').disabled=false;window.scrollTo(0,document.body.scrollHeight);
}
$('#go').onclick=send;
$('#in').onkeydown=e=>{if(e.key==='Enter')send()};
$('#model').onchange=()=>{hist=[];$('#chat').innerHTML='';add('ai','已切换到 '+$('#model').value)};
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
