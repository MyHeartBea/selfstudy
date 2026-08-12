import json
import sys
import urllib.request

sys.path.insert(0, r"C:\Users\Administrator\Documents\Codex\2026-08-08\new-chat\work\km\backend")

from app.services.ai_service import _wrap_math


sample = "思路：测试。$\n\n1.1$ 构造矩阵 $P$，已知 $\\alpha^T\\beta=0$ 与 $A^2\\beta=\\beta$。\n"
print("cleaned sample:")
print(_wrap_math(sample))


def get(path):
    req = urllib.request.Request("http://localhost:8000" + path, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def put(path, payload):
    req = urllib.request.Request(
        "http://localhost:8000" + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


data = get("/api/mistakes/41")["data"]
payload = {
    "subject_id": data["subject_id"],
    "sub_subject_id": data["sub_subject_id"],
    "question_type": data["question_type"],
    "question": data["question"],
    "option_a": data["option_a"] or "",
    "option_b": data["option_b"] or "",
    "option_c": data["option_c"] or "",
    "option_d": data["option_d"] or "",
    "correct_answer": data["correct_answer"] or "",
    "answer_aliases": data["answer_aliases"] or [],
    "analysis": (
        "思路：已知全部特征值和线性无关的特征向量，用 $B=P\\Lambda P^{-1}$ 还原矩阵。"
        "先把三个特征向量拼成矩阵 $P$，再求逆，最后做两次矩阵乘法并验证。\n\n"
        "1.1 构造 $P$ 与 $\\Lambda$：\n"
        "$P=[\\alpha_1,\\alpha_2,\\alpha_3]=\\begin{pmatrix}1&1&-1\\\\-1&1&0\\\\1&0&1\\end{pmatrix}$，"
        "$\\Lambda=\\mathrm{diag}(-2,1,1)$。\n\n"
        "2.1 求 $|P|$：\n"
        "$|P|=1\\times(1-0)-1\\times(-1-0)+(-1)\\times(0-1)=1+1+1=3$。\n\n"
        "2.2 由伴随矩阵求逆：\n"
        "$P^{-1}=\\dfrac{1}{3}\\begin{pmatrix}1&-1&1\\\\1&2&1\\\\-1&1&2\\end{pmatrix}$。\n\n"
        "3.1 先算 $\\Lambda P^{-1}$：\n"
        "$\\Lambda P^{-1}=\\begin{pmatrix}-2/3&2/3&-2/3\\\\1/3&2/3&1/3\\\\-1/3&1/3&2/3\\end{pmatrix}$。\n\n"
        "3.2 再算 $B=P(\\Lambda P^{-1})$：\n"
        "$B=\\begin{pmatrix}0&1&-1\\\\1&0&1\\\\-1&1&0\\end{pmatrix}$。\n\n"
        "4.1 验证：\n"
        "$B\\alpha_1=(-2,2,-2)^T=-2\\alpha_1$，"
        "$B\\alpha_2=(1,1,0)^T=\\alpha_2$，"
        "$B\\alpha_3=(-1,0,1)^T=\\alpha_3$，均符合题意。\n\n"
        "结论：$B=\\begin{pmatrix}0&1&-1\\\\1&0&1\\\\-1&1&0\\end{pmatrix}$。"
    ),
    "difficulty": data["difficulty"],
    "difficulty_points": data["difficulty_points"],
    "knowledge_tags": data["knowledge_tags"],
    "approach": data["approach"],
    "source": data["source"],
    "source_type": data["source_type"],
    "source_year": data["source_year"],
    "source_name": data["source_name"],
}

result = put("/api/mistakes/41", payload)
print("update:", result["code"], result["message"])
print("new analysis head:", (result["data"]["analysis"] or "")[:200])
