# 🧠 Kaggle Multi-Model LLM Server — My Fork

> **Two models, one URL, switch by name.** A free OpenAI-compatible LLM server running on Kaggle's T4 GPU and exposed through a Cloudflare tunnel. Connect any agent (Codex, Cline, Continue, Open WebUI, LangChain...) — no local GPU needed.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Kaggle](https://img.shields.io/badge/Kaggle-Free%20T4%20GPU-blue.svg)](https://www.kaggle.com/)

---

## 🙏 Attribution

This project is a fork of **[Tahsine/kaggle-llm-server](https://github.com/Tahsine/kaggle-llm-server)**, licensed under the MIT License. Original copyright © Tahsine. See [LICENSE](LICENSE) for full terms.

**Improvements in this fork:**
- ✅ **Two selectable models** with a switching gateway — change the `model` field, no client reconfiguration
- ✅ Added DeepSeek-V4-Pro-Qwen3.5-9B (uncensored) model via `1c_setup_deepseek.ipynb`
- ✅ Fixed `NameError: name 'MODEL_PATH' is not defined` — auto-detect username and dataset paths (old + new Kaggle layouts)
- ✅ Fixed the same username crash in all setup notebooks
- ✅ Upgraded `chat.py` with `--model` / `/model` switching and `--list-models`
- ✅ Added comprehensive agent integration guide

---

## Models

| Alias (`model` field) | Model | Strength |
|---|---|---|
| `qwen3.6-35b-a3b` | Qwen3.6-35B-A3B (MoE, multimodal) | General chat, vision, reasoning (default) |
| `deepseek-v4-pro-9b` | DeepSeek-V4-Pro-Qwen3.5-9B (Heretic, uncensored) **F16 full precision (~17 GB)** | Math/STEM, uncensored |

Only one model is in VRAM at a time (full speed). Switching loads the other (~10s–2min, first time only). The 9B uses the **F16 full-precision** weights by default — it loads alone in 30 GB VRAM. To use a smaller quant, edit `QUANT` in `1c_setup_deepseek.ipynb` (options: `F16` / `f16_q8_0` / `Q4_K_M`).

## Architecture

```
Agent (Codex/Cline/Continue/Open WebUI/chat.py)
   │  OpenAI API — one URL, choose model via "model" field
   ▼
Cloudflare Tunnel  →  Gateway :8080  →  llama-server :8081 (loads chosen model on demand)
```

## Repository structure

```
├── 1_setup_dataset.ipynb    # Once: download Qwen3.6-35B → Kaggle Dataset
├── 1b_setup_llama.ipynb     # Once: compile llama.cpp (b12182+) → Kaggle Dataset
├── 1c_setup_deepseek.ipynb  # Once: download DeepSeek 9B → Kaggle Dataset
├── 2_run_server.ipynb       # Each session: start gateway + models + tunnel
├── model_gateway.py         # The OpenAI-compatible multi-model switching gateway
├── chat.py                  # CLI client with model switching (text + images)
├── AGENT接入指南.md         # Connect Codex / Cline / Continue / Open WebUI / LangChain
├── 建仓与推送指南.md        # GitHub setup & push instructions
└── LICENSE                  # MIT (original author + fork attribution)
```

## Quick start

### 1. One-time setup (run each once on Kaggle)

| Notebook | Settings | Result |
|---|---|---|
| `1_setup_dataset.ipynb` | Internet ON, no GPU | Private dataset `qwen36-35b-a3b-gguf` |
| `1b_setup_llama.ipynb` | Internet ON, GPU T4 x1 | Private dataset `llama-cpp-bin` (latest llama.cpp) |
| `1c_setup_deepseek.ipynb` | Internet ON, no GPU | Private dataset `deepseek-v4-pro-9b-gguf` (F16 ~17 GB, ~10–30 min download) |

All auto-detect your username. Just **Run All**. (To skip setup, attach the public datasets by `tahsinekajolasalami` instead.)

> ⚠️ The 9B model uses the new `qwen3_5` architecture — requires llama.cpp **b12182+**. Re-run `1b_setup_llama.ipynb` if needed.

### 2. Run the server

Open `2_run_server.ipynb` → Settings: **GPU T4 x2**, Internet **ON**, attach the 3 datasets → **Run All**. After ~2–6 min you'll see the Cloudflare URL listing both models.

### 3. Connect any agent

```bash
pip install openai
python chat.py --url https://xxxx.trycloudflare.com --list-models
python chat.py --url https://xxxx.trycloudflare.com --model deepseek-v4-pro-9b
```
Base URL: `https://xxxx.trycloudflare.com/v1` · API Key: `none` · See **[AGENT接入指南.md](AGENT接入指南.md)** for Codex/Cline/Continue/Open WebUI/LangChain configs.

## Model switching API

```bash
# list models
curl https://xxxx.trycloudflare.com/v1/models

# use a specific model — just set "model"
curl https://xxxx.trycloudflare.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-pro-9b","messages":[{"role":"user","content":"Hi"}]}'
```

## Configuration

Each notebook's first code cell holds all settings (dataset names, context sizes, sampling params, model aliases). Username detection is automatic.

## Session limits

Kaggle free tier: 12h/session, 30h GPU/week. For headless 12h runs use **Save Version → Save and Run All (Commit)**.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Dataset not found` | Add datasets under notebook settings → Add Data |
| `qwen3_5` load error | Re-run `1b_setup_llama.ipynb` for llama.cpp b12182+ |
| `Unknown model` | Check exact alias with `/v1/models` |
| Switching is slow | First load of a model; subsequent requests reuse it |
| 502 / no response | Check Cell 5 log or `/tmp/llama-backend-stdout.log`; reduce context size |

## License & disclaimer

MIT — see [LICENSE](LICENSE). The `deepseek-v4-pro-9b` model is **decensored**; assess compliance with your local laws before use. Model weights: [Qwen License](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF).
