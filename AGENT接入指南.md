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

## 5. Chatbox / LM Studio / Chatterbox 等桌面客户端

- API 类型选 **OpenAI API**
- API Host: `https://xxxx.trycloudflare.com/v1`
- API Key: `none`
- Model: 选或填 `deepseek-v4-pro-9b` 等

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
