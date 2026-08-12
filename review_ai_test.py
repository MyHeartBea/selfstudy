import json
import urllib.request

BASE = "http://localhost:8000"


def call(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            if "application/json" in resp.headers.get("Content-Type", ""):
                return resp.status, json.loads(raw.decode("utf-8"))
            return resp.status, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


payload = {
    "subject_id": 3,
    "sub_subject_id": None,
    "question": "REVIEW API TEST question",
    "option_a": "a",
    "option_b": "b",
    "option_c": "c",
    "option_d": "d",
    "correct_answer": "C",
    "analysis": "test analysis",
    "difficulty": 3,
    "knowledge_tags": ["REVIEW_TEST_TAG"],
    "approach": "",
    "source": "review-test",
}

status, created = call("POST", "/api/mistakes", payload)
mid = created["data"]["id"]
print("create:", status, mid)

status, due = call("GET", "/api/reviews/today")
print("due_before:", status, len(due["data"]), "has_new=", any(x["id"] == mid for x in due["data"]))

status, r1 = call("POST", f"/api/mistakes/{mid}/review", {"result": True})
print(
    "review_correct:",
    status,
    "mastery=",
    r1["data"]["mastery_level"],
    "count=",
    r1["data"]["review_count"],
    "next=",
    r1["data"]["next_review_at"],
)

status, r2 = call("POST", f"/api/mistakes/{mid}/review", {"result": False})
print(
    "review_wrong:",
    status,
    "mastery=",
    r2["data"]["mastery_level"],
    "wrong=",
    r2["data"]["wrong_count"],
)

status, stats = call("GET", "/api/reviews/stats")
print(
    "review_stats:",
    status,
    "due=",
    stats["data"]["due_today"],
    "reviewed_today=",
    stats["data"]["reviewed_today"],
    "accuracy=",
    stats["data"]["accuracy_today"],
    "weakest=",
    [item["tag_name"] for item in stats["data"]["weakest_tags"]],
)

status, ai = call("POST", "/api/ai/analyze", {"text": "测试题目"})
print("ai_no_key:", status, ai["message"][:40])

status, ai_ocr = call("POST", "/api/ai/ocr", {"image_base64": "AAAA"})
print("ocr_no_key:", status, ai_ocr["message"][:40])

status, summary = call("POST", "/api/knowledge/1/auto-summarize")
print("summarize_no_key:", status, summary["message"][:40])

status, detail = call("GET", f"/api/mistakes/{mid}")
print(
    "detail_review_fields:",
    status,
    "mastery=",
    detail["data"]["mastery_level"],
    "next=",
    bool(detail["data"]["next_review_at"]),
)

# 清理测试数据：先删复习记录，再删错题和知识点
call("DELETE", f"/api/mistakes/{mid}")
status, tag_rows = call("GET", "/api/knowledge?tag=REVIEW_TEST_TAG")
for item in tag_rows["data"]:
    call("DELETE", f"/api/knowledge/{item['id']}")
print("cleanup done")

status, final = call("GET", "/api/mistakes")
print("final_count:", status, len(final["data"]))
