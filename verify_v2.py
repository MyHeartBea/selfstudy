import json
import sys
import urllib.request

BASE = "http://localhost:8000"


def call(method, path, body=None, timeout=5):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if "application/json" in resp.headers.get("Content-Type", ""):
                return resp.status, json.loads(raw.decode("utf-8"))
            return resp.status, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


status, data = call("GET", "/api/mistakes")
print("mistakes:", status, len(data["data"]), flush=True)

status, data = call("GET", "/api/reviews/today")
print("due_today:", status, len(data["data"]), flush=True)

status, data = call("GET", "/api/knowledge")
print("knowledge:", status, len(data["data"]), flush=True)

status, data = call("GET", "/api/reviews/stats")
print("review_stats:", status, data["data"]["due_today"], data["data"]["reviewed_today"], flush=True)

status, data = call("POST", "/api/ai/analyze", {"text": "测试"})
print("ai_config:", status, data["message"][:30], flush=True)

status, html = call("GET", "/")
print("home:", status, "has_app=", 'id="app"' in html, flush=True)
