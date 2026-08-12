import json
import urllib.request


def call(method, path, body=None, timeout=90):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        "http://localhost:8000" + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


question = (
    "已知一棵完全二叉树有 1001 个结点，则该二叉树的叶子结点个数是？"
    "A. 500 B. 501 C. 499 D. 502"
)

status, data = call("POST", "/api/ai/analyze", {"text": question})
print("status:", status)
if status == 200:
    item = data["data"]
    print("question:", item.get("question", "")[:40])
    print("correct:", item.get("correct_answer"))
    print("difficulty:", item.get("difficulty"))
    print("tags:", item.get("knowledge_tags"))
    print("approach:", item.get("approach"))
    print("analysis_len:", len(item.get("analysis", "")))
else:
    print("message:", data.get("message"))

with urllib.request.urlopen("http://localhost:8000/api/mistakes", timeout=5) as resp:
    mistakes = json.loads(resp.read().decode("utf-8"))
print("mistakes_unchanged:", len(mistakes["data"]))
