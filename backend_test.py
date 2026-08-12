import json
import urllib.parse
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


status, home = call("GET", "/")
print("home:", status, "has_app=", 'id="app"' in home)

status, subjects = call("GET", "/api/subjects")
print("subjects:", status, len(subjects["data"]), [s["name"] for s in subjects["data"]])

status, mistakes = call("GET", "/api/mistakes")
print("mistakes:", status, len(mistakes["data"]))

status, detail = call("GET", "/api/mistakes/1")
extra = detail["data"]["knowledge_extra"]
print(
    "detail1:",
    status,
    "extra=",
    extra["tag_name"] if extra else None,
    "related=",
    len(detail["data"]["related_mistakes"]),
)

status, bytag = call(
    "GET",
    "/api/knowledge/by-tag?tag=" + urllib.parse.quote("二叉树遍历"),
)
print("bytag:", status, bytag["data"]["tag_name"])

status, stats = call("GET", "/api/stats")
print(
    "stats:",
    status,
    stats["data"]["total_mistakes"],
    len(stats["data"]["by_subject"]),
)

payload = {
    "subject_id": 4,
    "sub_subject_id": 1,
    "question": "测试：链式存储的二叉树结点数量统计方式是？",
    "option_a": "A1",
    "option_b": "B1",
    "option_c": "C1",
    "option_d": "D1",
    "correct_answer": "B",
    "analysis": "测试解析",
    "difficulty": 4,
    "knowledge_tags": ["测试标签XYZ", "二叉树遍历"],
    "approach": "递归",
    "source": "测试",
}
status, created = call("POST", "/api/mistakes", payload)
new_id = created["data"]["id"]
print("create:", status, new_id, created["data"]["knowledge_tags"])

status, updated = call(
    "PUT",
    f"/api/mistakes/{new_id}",
    {**payload, "correct_answer": "D", "difficulty": 5},
)
print("update:", status, updated["data"]["correct_answer"], updated["data"]["difficulty"])

status, tagrow = call(
    "GET",
    "/api/knowledge/by-tag?tag=" + urllib.parse.quote("测试标签XYZ"),
)
print("auto_tag:", status, tagrow["data"]["id"], repr(tagrow["data"]["summary"]))

import_payload = {
    "mistakes": [
        {
            "subject_id": 2,
            "sub_subject_id": None,
            "question": "导入测试题：The book ______ I bought is useful.",
            "option_a": "which",
            "option_b": "who",
            "option_c": "what",
            "option_d": "where",
            "correct_answer": "A",
            "analysis": "",
            "difficulty": 2,
            "knowledge_tags": ["导入标签TEST"],
            "approach": "",
            "source": "import",
        }
    ]
}
status, imported = call("POST", "/api/import", import_payload)
print("import:", status, imported["data"]["created"], imported["data"]["failed"])

status, export = call("GET", "/api/export")
print("export:", status, len(export["data"]["mistakes"]), len(export["data"]["knowledge"]))

status, _ = call("DELETE", f"/api/mistakes/{new_id}")
print("delete_mistake:", status)
status, _ = call("DELETE", f"/api/knowledge/{tagrow['data']['id']}")
print("delete_tag:", status)

status, search = call("GET", "/api/mistakes?search=" + urllib.parse.quote("导入测试题"))
for item in search["data"]:
    call("DELETE", f"/api/mistakes/{item['id']}")
tag_rows = call("GET", "/api/knowledge?tag=" + urllib.parse.quote("导入标签TEST"))[1]["data"]
for item in tag_rows:
    call("DELETE", f"/api/knowledge/{item['id']}")

status, final = call("GET", "/api/mistakes")
print("final_count:", status, len(final["data"]))
