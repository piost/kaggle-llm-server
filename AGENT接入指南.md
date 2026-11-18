# Agent 接入指南（多模型 / OpenAI 兼容）

服务器暴露的是**标准 OpenAI 兼容 API**，几乎所有现代 Agent / 工具都能直接接入。

## 通用连接参数（所有工具都一样）

| 参数 | 值 |
|---|---|
| Base URL | `https://xxxx.trycloudflare.com/v1` |
| API Key | `none`（任意值都行，服务器不校验） |
| Model | `qwen3.6-35b-a3b` 或 `deepseek-v4-pro-9b` |

> URL 每次启动会变，从 notebook 的 Cell 6 输出里复制最新的。
> **切换模型不用改 URL**，只改 model 名即可。

可用模型：
- `qwen3.6-35b-a3b` — Qwen3.6-35B-A3B，通用/视觉/推理（默认）
- `deepseek-v4-pro-9b` — DeepSeek-V4-Pro-Qwen3.5-9B，数学/STEM/无审查（**F16 全精度 ~17 GB**，单独加载占满显存）

---

## 1. OpenAI Codex CLI

```bash
# 方法 A：命令行参数
codex --provider-url "https://xxxx.trycloudflare.com/v1" \
      --model "qwen3.6-35b-a3b"

# 方法 B：配置文件 ~/.codex/config.toml
[model_providers.kaggle]
name = "kaggle"
base_url = "https://xxxx.trycloudflare.com/v1"
env_key = "OPENAI_API_KEY"   # 随便设个环境变量名

[profiles.qwen]
model_provider = "kaggle"
model = "qwen3.6-35b-a3b"

[profiles.deepseek]
model_provider = "kaggle"
model = "deepseek-v4-pro-9b"

# 使用：codex --profile deepseek
```
> 若提示需要 API key，`export OPENAI_API_KEY=none` 即可。

## 2. Cline（VS Code 扩展）

- API Provider: **OpenAI Compatible**
- Base URL: `https://xxxx.trycloudflare.com/v1`
- API Key: `none`
- Model ID: `qwen3.6-35b-a3b`（或 deepseek）
- 切换：改 Model ID 字段

## 3. Continue（VS Code / JetBrains）

`~/.continue/config.yaml`:
```yaml
models:
  - name: qwen-kaggle
    provider: openai
    model: qwen3.6-35b-a3b
    apiBase: https://xxxx.trycloudflare.com/v1
    apiKey: none
  - name: deepseek-kaggle
    provider: openai
    model: deepseek-v4-pro-9b
    apiBase: https://xxxx.trycloudflare.com/v1
    apiKey: none
```
两个都配上，在 Continue 面板里下拉切换。

## 4. Open WebUI

Settings → Connections → OpenAI API:
- URL: `https://xxxx.trycloudflare.com/v1`
- Key: `none`
- 保存后模型列表会自动出现两个模型，在下拉框里切换。

## 5. Chatbox（最省事的图形聊天窗口，推荐新手）

官网免费下载：`https://chatboxai.app/zh`（Windows 选 .exe）。它自带模型下拉切换框，最适合"用哪个点哪个"。

配置一次即可（左下角齿轮 → 模型提供方 → 添加）：

| 字段 | 填什么 |
|---|---|
| 提供方名称 | 随便，如 `My Kaggle` |
| API 模式 | **OpenAI API 兼容** |
| API 主机 / Host | `https://xxxx.trycloudflare.com/v1`（换成 Cell 6 新 URL）|
| API Key | `none`（随便填，服务器不校验）|
| 模型 | 手动添加两个：`qwen3.6-35b-a3b`、`deepseek-v4-pro-9b` |

保存 → 点「检查」看到连接成功 → 回主界面。之后在**聊天窗口顶部的模型下拉框**里选一个即可，切模型不用改 URL。

> 注意：Kaggle 会话停掉再启动会生成**新 URL**，届时只需回这里把 API 主机换成新的，模型名不用动。

同类桌面客户端（LM Studio / Chatterbox / Cherry Studio）配置一样：API 类型选 OpenAI，Host 填上面地址，Key 填 `none`，模型名手动加。

## 6. Python (openai SDK)

```python
from openai import OpenAI
client = OpenAI(base_url="https://xxxx.trycloudflare.com/v1", api_key="none")

resp = client.chat.completions.create(
    model="deepseek-v4-pro-9b",   # 改这里切换模型
    messages=[{"role": "user", "content": "Hello"}],
)
print(resp.choices[0].message.content)
```

## 7. LangChain

```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    base_url="https://xxxx.trycloudflare.com/v1",
    api_key="none",
    model="qwen3.6-35b-a3b",
)
```

## 8. 自带 chat.py（本仓库）

```bash
pip install openai
python chat.py --url https://xxxx.trycloudflare.com
python chat.py --url https://xxxx.trycloudflare.com --model deepseek-v4-pro-9b
python chat.py --url https://xxxx.trycloudflare.com --list-models
```
对话中输入 `/models` 看模型，`/model deepseek-v4-pro-9b` 切换。

---

## 会话能活多久 / 要不要一直开着电脑

**不用一直开着电脑。** notebook 跑在 Kaggle 云端，和本地电脑完全无关——关掉浏览器标签页、关机、断网都不影响云端内核继续运行。

但 Kaggle 免费版有几条硬规则，决定了它**不是 7×24 常驻服务**：

| 限制 | 数值 | 对你的影响 |
|---|---|---|
| 单次会话最长 | **12 小时** | 到点强制停止，无法延长 |
| 交互会话闲置 | 约 20–60 分钟 | 浏览器长时间无操作可能自动停 |
| 每周 GPU 配额 | 约 30 小时 | T4×2 开着就计时，用完等下周 |
| 公网 URL | **每次启动都变** | 客户端要跟着换新 URL |

**Cell 7 的保活循环**每 5 分钟做一次健康检查，让会话一直处于"执行中"，通常能顶住闲置检测、撑到 12 小时上限。所以正常用法：启动后该干嘛干嘛，电脑随便关。

### 会话断了怎么办（不用慌）

重新打开 notebook → **Run All** 即可，**几分钟就好**——编译好的二进制和模型都在你建好的数据集里，不用重新下载、不用重新编译 26 分钟。

### 想更稳一点：用后台运行

菜单 **File → Save & Run All** 会以独立后台会话运行，官方保证关闭标签页后仍继续（同样 12 小时上限）。新 URL 到该版本的输出日志里找。

### 想要真正 7×24 + 固定 URL

Kaggle 免费版做不到（12h 硬上限 + 动态 URL + 周配额）。正经方案是付费云 GPU 常驻，或本地常驻机器 + Cloudflare 固定隧道（Named Tunnel）。免费阶段的用法就是"用完再启"，接受 URL 会变。

---

## 切换模型的两种方式

1. **客户端指定**（推荐）：每个请求带不同的 `model` 字段，网关自动加载对应模型。首次切到某模型需等 10s~2min 加载，之后同模型请求直接复用。
2. **查询当前模型**：`GET /v1/model` 返回 `{"current_model": "..."}`。

## 常见问题

| 现象 | 原因 / 解决 |
|---|---|
| 返回 `Unknown model` | model 名拼错了，用 `/v1/models` 查准确名字 |
| 切换后等很久 | 首次加载模型到显存，正常，之后就快 |
| 502 / 无响应 | 后端加载失败，看 notebook Cell 5 日志或 `/tmp/llama-backend-stdout.log` |
| qwen3_5 模型加载报错 | llama.cpp 版本太旧，重跑 `1b_setup_llama.ipynb` 编译最新版 |
| thinking 模式 | 请求里加 `extra_body={"chat_template_kwargs":{"enable_thinking": true}}` |

## 无审查模型说明

`deepseek-v4-pro-9b` 是去审查（decensored）模型，可能产生未被过滤的内容。请自行评估合规风险并遵守当地法律。它主要用于数学/STEM 推理。
