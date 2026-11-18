# ============================================================
# 一键给当前 Kaggle 服务加「网页聊天窗口」
# 用法：在 2_run_server.ipynb 最底部新增一个代码单元格，
#       把本文件全部内容复制进去，运行。刷新浏览器即可。
# 效果：URL 不变、不用重跑 notebook、10 秒生效。
# ============================================================
import os, json, subprocess, time

GP = '/kaggle/working/model_gateway.py'
s = open(GP, encoding='utf-8').read()

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

if 'WEB_UI = ' in s:
    print('已经打过补丁，跳过注入')
else:
    anchor = 'def log(msg):'
    assert anchor in s, '未找到网关锚点，请确认运行的是 2_run_server 生成的网关'
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
    assert old in s, '未找到路由代码块，网关版本不匹配'
    s = s.replace(old, new, 1)
    open(GP, 'w', encoding='utf-8').write(s)
    print('补丁已写入 model_gateway.py')

# 用当前 kernel 里的配置重建环境变量，确保重启后网关配置不丢
os.environ['MODEL_CONFIGS'] = json.dumps(MODEL_CONFIGS, ensure_ascii=False)
os.environ.update(DEFAULT_MODEL=DEFAULT_MODEL, GATEWAY_PORT=str(PORT),
                  BACKEND_PORT=str(BACKEND_PORT), LLAMA_SERVER=str(LLAMA_SERVER))

# 重启网关（Cloudflare 隧道指向 8080，URL 不变）
subprocess.run(['pkill', '-f', 'model_gateway.py'], capture_output=True)
time.sleep(2)
subprocess.Popen(['python', GP], stdout=open('/tmp/gateway.log', 'w'),
                 stderr=subprocess.STDOUT, env={**os.environ}, start_new_session=True)
time.sleep(4)
import requests as _rq
print(_rq.get('http://localhost:%s/health' % PORT, timeout=5).json())
print('完成：刷新浏览器打开原来的 URL，就是聊天窗口了')
