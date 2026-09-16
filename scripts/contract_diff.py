"""前端契约对照工具：把后端 API 的**响应形状**取样成基线，并在切换前后做结构化 diff。

为什么需要它
------------
v3 前端要复用 v2 的后端与同一张数据库。切换时最怕的不是"页面崩了"（那种一眼能看见），
而是**静默的形状漂移**：某个接口少了一个字段、某个数组变成了对象、某个数字变成了字符串 ——
页面照样渲染，只是数据不对。这个脚本把"数据准确性"变成可验证的东西：

  1) 采样：对一批只读端点发请求，把响应递归折叠成 **形状签名**（键名 + 类型，不含具体值）
  2) 比对：`--baseline v2.json --target v3.json` 做结构化 diff，任何增删改都列出路径
  3) 退出码非 0 即视为不通过，可直接接进 CI 或切换前的手工检查

只读、无副作用：不写库、不改数据。默认打本机 8000（v2 与 v3 共用同一个后端，
所以这里真正校验的是"前端依赖的字段契约"有没有被前端开发过程中的任何改动破坏）。

用法
----
  python scripts/contract_diff.py --dump baseline.json          # 采样并写基线
  python scripts/contract_diff.py --check baseline.json         # 与基线比对（切换前跑）
  python scripts/contract_diff.py --dump a.json --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

# 只读端点清单：(名称, 路径, 期望的 data 类型)
# 期望类型用于抓"形状级"回归：数组接口返回对象、分页对象返回数组，这类错误页面不会报错。
ENDPOINTS: list[tuple[str, str, str]] = [
    ("health", "/api/health", "dict"),
    ("dashboard", "/api/dashboard", "dict"),
    ("stats", "/api/stats", "dict"),
    ("subjects", "/api/subjects", "list"),
    ("sub_subjects", "/api/sub_subjects", "list"),
    ("sub_subjects.filtered", "/api/sub_subjects?subject_id=1", "list"),
    ("subject_profile", "/api/subjects/1/profile", "dict"),
    ("mistakes.bare", "/api/mistakes", "list"),
    ("mistakes.paged", "/api/mistakes?page=1&page_size=5", "dict"),
    ("mistakes.search", "/api/mistakes?search=%E6%B5%8B%E8%AF%95&page=1", "dict"),
    ("approaches", "/api/mistakes/approaches", "list"),
    ("knowledge.paged", "/api/knowledge?page=1&page_size=5", "dict"),
    ("knowledge.tags", "/api/knowledge/tags?limit=5", "list"),
    ("knowledge.by_tag", "/api/knowledge/by-tag?tag=%E5%AF%BC%E6%95%B0", "dict"),
    ("formulas", "/api/formulas", "list"),
    ("vocab.paged", "/api/vocab?page=1&page_size=5", "dict"),
    ("vocab.stats", "/api/vocab/stats", "dict"),
    ("vocab.due", "/api/vocab/due?limit=5", "list"),
    ("reviews.today", "/api/reviews/today", "dict"),
    ("reviews.stats", "/api/reviews/stats", "dict"),
    ("reviews.forecast", "/api/reviews/forecast?days=14", "dict"),
    ("reviews.calendar", "/api/reviews/calendar?days=30", "list"),
    # 练习接口返回**裸数组**（ReviewView 里明确兼容"数组 / {items} 两种"）
    ("reviews.practice", "/api/reviews/practice?count=3", "list"),
    ("reviews.practice.mock", "/api/reviews/practice?mode=mock&count=3", "list"),
    ("mocks", "/api/mocks?limit=3", "list"),
    ("papers", "/api/papers", "list"),
    ("papers.scan", "/api/papers/scan", "list"),
    ("export", "/api/export", "dict"),
]

# 形状签名里需要如实区分"标量"和"空容器"，但**不**记录具体值（否则每次跑都不同）
SCALAR = (str, int, float, bool, type(None))


def shape_of(value, depth: int = 0):
    """把任意 JSON 值折叠成形状：dict → 各键的形状（按 key 排序）；list → [元素形状] 或 []。"""
    if depth > 8:
        return "..."
    if isinstance(value, dict):
        return {k: shape_of(v, depth + 1) for k, v in sorted(value.items())}
    if isinstance(value, list):
        if not value:
            return []
        # 只取前 3 个元素的形状并集，避免超大数组把基线撑爆
        seen = []
        for item in value[:3]:
            s = shape_of(item, depth + 1)
            if s not in seen:
                seen.append(s)
        return seen if len(seen) > 1 else seen[0]
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def fetch(base_url: str, path: str, timeout: float = 30.0):
    url = base_url.rstrip("/") + path
    req = urllib.request.Request(url, headers={"User-Agent": "km-contract-diff"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
    except Exception as exc:  # 连接失败等
        return {"status": None, "error": f"{type(exc).__name__}: {exc}", "shape": None, "data_type": None}
    try:
        body = json.loads(raw)
    except ValueError:
        return {"status": status, "error": "响应不是 JSON", "shape": None, "data_type": None}
    data = body.get("data") if isinstance(body, dict) else None
    return {
        "status": status,
        "code": body.get("code") if isinstance(body, dict) else None,
        "data_type": type(data).__name__,
        "shape": shape_of(data),
    }


def collect(base_url: str) -> dict:
    out = {}
    for name, path, expect in ENDPOINTS:
        probe = fetch(base_url, path)
        probe["path"] = path
        probe["expect"] = expect
        out[name] = probe
        flag = ""
        if probe.get("error"):
            flag = f"  !! {probe['error']}"
        elif probe["data_type"] != expect:
            flag = f"  !! data 类型 {probe['data_type']} != 期望 {expect}"
        print(f"  {name:26s} {str(probe.get('status')):>4}  data={probe.get('data_type'):<8}{flag}")
    return out


def walk_diff(a, b, path: str, out: list[str]) -> None:
    """递归比较两个形状，把差异写进 out（带路径）。"""
    if type(a) is not type(b):
        out.append(f"{path}: 类型变化 {type(a).__name__} -> {type(b).__name__}  ({a!r} -> {b!r})")
        return
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}.{k}: **新增** {b[k]!r}")
            elif k not in b:
                out.append(f"{path}.{k}: **缺失**（原来是 {a[k]!r}）")
            else:
                walk_diff(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: 数组元素形状数变化 {len(a)} -> {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            walk_diff(x, y, f"{path}[{i}]", out)
    else:
        if a != b:
            out.append(f"{path}: {a!r} -> {b!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description="km-v2 前端契约形状对照")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--dump", metavar="FILE", help="采样并写入基线文件")
    ap.add_argument("--check", metavar="FILE", help="与已有基线比对")
    ap.add_argument(
        "--no-strict",
        action="store_true",
        help="首次采样时用：只报告 data 类型不符，不让退出码非 0（基线与期望的已知差异不作为失败）",
    )
    args = ap.parse_args()

    if not args.dump and not args.check:
        ap.error("需要 --dump 或 --check 之一")

    print(f"采样 {args.base_url}（{len(ENDPOINTS)} 个只读端点）")
    current = collect(args.base_url)

    failed = [n for n, p in current.items() if p.get("error")]
    mismatched = [n for n, p in current.items() if not p.get("error") and p["data_type"] != p["expect"]]

    if args.dump:
        with open(args.dump, "w", encoding="utf-8") as f:
            json.dump({"base_url": args.base_url, "endpoints": current}, f, ensure_ascii=False, indent=2)
        print(f"\n基线已写入 {args.dump}")

    code = 0
    if args.check:
        with open(args.check, encoding="utf-8") as f:
            baseline = json.load(f)["endpoints"]
        diffs: list[str] = []
        for name, old in baseline.items():
            new = current.get(name)
            if new is None:
                diffs.append(f"{name}: 端点从采样清单中消失")
                continue
            for field in ("status", "code", "data_type"):
                if old.get(field) != new.get(field):
                    diffs.append(f"{name}.{field}: {old.get(field)!r} -> {new.get(field)!r}")
            walk_diff(old.get("shape"), new.get("shape"), name, diffs)

        print("\n=== 契约差异 ===")
        if diffs:
            for line in diffs:
                print("  -", line)
            print(f"\n不通过：{len(diffs)} 处差异")
            code = 1
        else:
            print("  无差异")

    if failed:
        print(f"\n请求失败 {len(failed)} 个：{', '.join(failed)}")
        code = 1
    if mismatched:
        print(f"data 类型不符 {len(mismatched)} 个：{', '.join(mismatched)}")
        if not args.no_strict:
            code = 1

    print("\n结论：" + ("通过" if code == 0 else "不通过"))
    return code


if __name__ == "__main__":
    sys.exit(main())
