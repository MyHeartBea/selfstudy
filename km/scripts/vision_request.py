"""Codex 可复用的三视觉模型调用工具：GLM-4.6V-Flash -> Agnes-2.0-Flash -> Agnes-2.5-Flash。"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

DEFAULT_ENV = Path(
    r"C:\Users\Administrator\Documents\Codex\2026-08-08\new-chat\work\km\backend\.env"
)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def build_providers():
    result = []
    for channel, model_key, base_key, key_key in (
        ("glm", "AI_VISION_MODEL", "AI_VISION_BASE_URL", "AI_VISION_API_KEY"),
        (
            "glm-fallback",
            "AI_VISION_MODEL_FALLBACK",
            "AI_VISION_BASE_URL",
            "AI_VISION_API_KEY",
        ),
        (
            "agnes2",
            "AI_VISION_2_MODEL",
            "AI_VISION_2_BASE_URL",
            "AI_VISION_2_API_KEY",
        ),
        (
            "agnes2-fallback",
            "AI_VISION_2_MODEL_FALLBACK",
            "AI_VISION_2_BASE_URL",
            "AI_VISION_2_API_KEY",
        ),
        (
            "agnes3",
            "AI_VISION_3_MODEL",
            "AI_VISION_3_BASE_URL",
            "AI_VISION_3_API_KEY",
        ),
    ):
        model = env(model_key)
        if model:
            result.append((channel, model, env(base_key), env(key_key)))
    return result


def call_model(
    channel,
    model,
    base_url,
    api_key,
    image_data_url,
    prompt,
    timeout,
):
    url = (base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def main() -> int:
    parser = argparse.ArgumentParser(description="调用三视觉模型识别图片")
    parser.add_argument("--image", required=True, help="图片文件路径")
    parser.add_argument(
        "--prompt",
        default="请完整提取图片中的内容：如果是题目，请提取题干、选项和答案；否则描述图片主要内容。",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--timeout", type=int, default=30, help="单通道超时秒数")
    parser.add_argument("--total-timeout", type=int, default=90, help="整体超时秒数")
    args = parser.parse_args()

    load_env(DEFAULT_ENV)
    image_path = Path(args.image)
    if not image_path.exists():
        print(json.dumps({"ok": False, "error": "图片不存在"}, ensure_ascii=False))
        return 1

    suffix_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    mime = suffix_map.get(image_path.suffix.lower(), "image/png")
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    image_data_url = f"data:{mime};base64,{image_b64}"

    providers = build_providers()
    if not providers:
        print(
            json.dumps(
                {"ok": False, "error": "未配置视觉模型 API"},
                ensure_ascii=False,
            )
        )
        return 1

    started = time.monotonic()
    errors = []
    executor = ThreadPoolExecutor(max_workers=len(providers))
    futures = {
        executor.submit(
            call_model,
            channel,
            model,
            base_url,
            api_key,
            image_data_url,
            args.prompt,
            args.timeout,
        ): channel
        for channel, model, base_url, api_key in providers
    }
    try:
        pending = set(futures)
        while pending:
            remaining = max(
                0.1,
                min(2.0, args.total_timeout - (time.monotonic() - started)),
            )
            done, _ = wait(
                pending,
                timeout=remaining,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                if time.monotonic() - started >= args.total_timeout:
                    break
                continue
            for future in done:
                pending.discard(future)
                channel = futures[future]
                try:
                    text = future.result()
                    if args.json:
                        print(
                            json.dumps(
                                {"ok": True, "provider": channel, "text": text},
                                ensure_ascii=False,
                            )
                        )
                    else:
                        print(text)
                    return 0
                except Exception as exc:
                    errors.append(f"{channel}: {exc}")
            if time.monotonic() - started >= args.total_timeout:
                break
    finally:
        executor.shutdown(wait=False)

    print(
        json.dumps(
            {"ok": False, "errors": errors[:3]},
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
