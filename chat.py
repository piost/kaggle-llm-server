#!/usr/bin/env python3
"""
chat.py - Interactive CLI client for the multi-model LLM server on Kaggle

Usage:
    python chat.py --url https://xxxx.trycloudflare.com
    python chat.py --url https://xxxx.trycloudflare.com --model deepseek-v4-pro-9b
    python chat.py --url https://xxxx.trycloudflare.com --list-models

Commands during conversation:
    /model <name>             -> switch the active model (e.g. /model deepseek-v4-pro-9b)
    /models                   -> list available models from the server
    /image <path>             -> attach an image to your next message
    /clear                    -> clear conversation history
    /history                  -> show conversation
    /exit  or  Ctrl+C         -> quit
"""

import argparse
import base64
import json
import sys
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("openai package not found. Run: pip install openai")
    sys.exit(1)


def encode_image(path: str):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    suffix = p.suffix.lower().lstrip(".")
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
    mime = mime_map.get(suffix, "image/jpeg")
    with open(p, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{data}", mime


def build_user_message(text: str, image_path):
    if image_path:
        data_uri, _ = encode_image(image_path)
        return {"role": "user", "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ]}
    return {"role": "user", "content": text}


def print_history(history):
    if not history:
        print("  (empty)"); return
    for i, msg in enumerate(history):
        role = msg["role"].upper()
        if isinstance(msg["content"], str):
            preview = msg["content"][:120].replace("\n", " ")
        else:
            parts = [c["text"] for c in msg["content"] if c.get("type") == "text"]
            has_img = any(c.get("type") == "image_url" for c in msg["content"])
            preview = " ".join(parts)[:120] + ("  [+ image]" if has_img else "")
        print(f"  [{i}] {role}: {preview}")


def main():
    parser = argparse.ArgumentParser(description="Chat client for the multi-model Kaggle LLM server")
    parser.add_argument("--url", required=True, help="Your Cloudflare tunnel URL")
    parser.add_argument("--model", default=None,
                        help="Model alias to use (e.g. qwen3.6-35b-a3b, deepseek-v4-pro-9b)")
    parser.add_argument("--list-models", action="store_true", help="List models and exit")
    parser.add_argument("--thinking", action="store_true", help="Enable thinking mode")
    parser.add_argument("--system", default="You are a helpful assistant.", help="System prompt")
    parser.add_argument("--max-tokens", type=int, default=2048, help="Max tokens per response")
    args = parser.parse_args()

    base_url = args.url.rstrip("/") + "/v1"
    client = OpenAI(base_url=base_url, api_key="none")

    print(f"\nConnecting to {base_url} ...")
    try:
        models = [m.id for m in client.models.list().data]
        print(f"Connected. Models: {', '.join(models)}")
    except Exception as e:
        print(f"Could not connect: {e}")
        sys.exit(1)

    if args.list_models:
        for m in models:
            print("  -", m)
        return

    active_model = args.model or (models[0] if models else "qwen3.6-35b-a3b")
    if active_model not in models:
        print(f"Warning: '{active_model}' not in server model list. Using it anyway.")

    history = [{"role": "system", "content": args.system}]
    pending_image = None

    print(f"\n{'-'*55}")
    print(f"  Model   : {active_model}")
    print(f"  Mode    : {'thinking' if args.thinking else 'direct'}")
    print(f"{'-'*55}")
    print("  Commands: /model <name>  /models  /image <path>  /clear  /history  /exit")
    print(f"{'-'*55}\n")

    while True:
        try:
            label = f"[image: {Path(pending_image).name}] You: " if pending_image else "You: "
            user_input = input(label).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nBye!"); break
        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            if cmd == "/exit":
                print("Bye!"); break
            elif cmd == "/clear":
                history = [{"role": "system", "content": args.system}]
                pending_image = None
                print("Conversation cleared.\n")
            elif cmd == "/history":
                print("\nConversation history:"); print_history(history); print()
            elif cmd == "/models":
                print("\nAvailable models:")
                for m in models:
                    print("  -", m + ("  <-- current" if m == active_model else ""))
                print()
            elif cmd == "/model":
                if len(parts) < 2:
                    print("  Usage: /model <name>   (see /models)\n")
                else:
                    active_model = parts[1].strip()
                    print(f"  Switched to: {active_model}\n")
            elif cmd == "/image":
                if len(parts) < 2:
                    print("  Usage: /image path/to/file.jpg\n")
                else:
                    img = parts[1].strip()
                    try:
                        encode_image(img)
                        pending_image = img
                        print(f"  Image queued: {img}\n")
                    except FileNotFoundError as e:
                        print(f"  {e}\n")
            else:
                print(f"  Unknown command: {cmd}\n")
            continue

        user_msg = build_user_message(user_input, pending_image)
        pending_image = None
        history.append(user_msg)
        print("\nAssistant: ", end="", flush=True)
        try:
            stream = client.chat.completions.create(
                model=active_model,
                messages=history,
                max_tokens=args.max_tokens,
                stream=True,
                extra_body={
                    "chat_template_kwargs": {"enable_thinking": args.thinking},
                    "temperature": 1.0 if args.thinking else 0.7,
                    "top_p": 0.95 if args.thinking else 0.8,
                },
            )
            full = ""
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    print(delta.content, end="", flush=True)
                    full += delta.content
            print("\n")
            history.append({"role": "assistant", "content": full})
        except KeyboardInterrupt:
            print("\n\nResponse interrupted.\n")
            history.pop()
        except Exception as e:
            print(f"\nAPI error: {e}\n")
            history.pop()


if __name__ == "__main__":
    main()
