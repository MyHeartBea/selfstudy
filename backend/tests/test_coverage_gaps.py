"""测试盲区补齐（P2）：/api/formulas 全套 CRUD、/api/dashboard 聚合、
app/vocab_filter.py 收录规则、AI 错因周报的缓存链路 —— 此前这四块一个用例都没有。
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_connection, init_database
from app.main import app
from app.services import ai_service
from app.vocab_filter import should_reject

client = TestClient(app)


def _post_ok(url, body):
    r = client.post(url, json=body)
    assert r.status_code == 200, r.text
    return r.json()


class FormulasApiTest(unittest.TestCase):
    """公式库端点此前零覆盖；PUT/DELETE 的 404 与重复标题的 400 都在这钉住。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def test_create_list_search_and_filter(self):
        # seed_data 会预置一批默认公式，断言一律用"我造的这条在不在"，不做全量相等
        created = _post_ok("/api/formulas", {"title": "泰勒公式·测试甲", "content": "f(x)=∑"})
        self.assertIn("id", created["data"])
        _post_ok(
            "/api/formulas",
            {"category": "线性代数", "title": "行列式展开·测试甲", "content": "|A|"},
        )

        r = client.get("/api/formulas")
        self.assertEqual(r.status_code, 200)
        titles = [item["title"] for item in r.json()["data"]]
        self.assertIn("泰勒公式·测试甲", titles)
        self.assertIn("行列式展开·测试甲", titles)

        by_category = client.get("/api/formulas", params={"category": "线性代数"}).json()["data"]
        self.assertIn("行列式展开·测试甲", [i["title"] for i in by_category])
        self.assertTrue(all(i["category"] == "线性代数" for i in by_category))

        by_search = client.get("/api/formulas", params={"search": "测试甲"}).json()["data"]
        self.assertEqual(len(by_search), 2)
        self.assertEqual({i["title"] for i in by_search}, {"泰勒公式·测试甲", "行列式展开·测试甲"})

    def test_duplicate_title_is_400(self):
        _post_ok("/api/formulas", {"title": "唯一标题甲", "content": "x"})
        r = client.post("/api/formulas", json={"title": "唯一标题甲", "content": "y"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("已存在", r.json()["message"])

    def test_update_and_delete_with_404s(self):
        created = _post_ok("/api/formulas", {"title": "待改公式", "content": "旧"})["data"]
        r = client.put(
            f"/api/formulas/{created['id']}", json={"title": "待改公式", "content": "新"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["content"], "新")

        self.assertEqual(
            client.put("/api/formulas/999999", json={"title": "x", "content": "y"}).status_code, 404
        )

        r = client.delete(f"/api/formulas/{created['id']}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(client.delete(f"/api/formulas/{created['id']}").status_code, 404)


class DashboardTest(unittest.TestCase):
    """与同套件其他类一致：**每个类自建临时库**，绝不借用上一个类的 DB_PATH——
    类之间临时目录可能已被清理（组合运行实测"no such table"假红），借用必炸。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def test_dashboard_returns_stats_and_reviews_maps(self):
        r = client.get("/api/dashboard")
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertIsInstance(data["stats"], dict)
        self.assertIsInstance(data["reviews"], dict)


class VocabFilterTest(unittest.TestCase):
    """收录过滤规则：钉住"宁可漏判也不误杀"的几条关键取舍。"""

    def test_basic_words_rejected(self):
        for w in ("system", "easy", "path", "accomplish", "legally", "existing"):
            rejected, _ = should_reject(w, "word")
            self.assertTrue(rejected, w)

    def test_valuable_word_is_kept_even_if_short(self):
        # 刻意不做"长度<=4 就删"：hurt/tend/lack/rate 是有价值的考研词（试运行误杀史）
        rejected, _ = should_reject("tend", "word")
        self.assertFalse(rejected)

    def test_empty_is_rejected(self):
        self.assertTrue(should_reject("", "word")[0])
        self.assertTrue(should_reject("   ", "phrase")[0])

    def test_whole_sentence_rejected(self):
        rejected, reason = should_reject("who would make some money and then go home", "phrase")
        self.assertTrue(rejected)
        self.assertIn("词数", reason)

    def test_ellipsis_slot_phrase_is_kept(self):
        # "hail ... as ..." 的省略号是空槽位（结构搭配），恰是最该记的 —— 不许当句子误杀
        rejected, _ = should_reject("hail ... as ...", "phrase")
        self.assertFalse(rejected)

    def test_all_basic_phrase_is_kept_by_design(self):
        # 刻意不判"整条全是基础词"：hold up / go home / all but 是真搭配（试运行误杀史）
        rejected, _ = should_reject("go home", "phrase")
        self.assertFalse(rejected)

    def test_sentence_punct_rejected(self):
        rejected, _ = should_reject("Take the first step.", "phrase")
        self.assertTrue(rejected)


class WeeklyReportCacheTest(unittest.TestCase):
    """周报缓存链路：空周不调 AI、命中缓存不重烧、force=1 重烧并清旧日期缓存。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def _seed_wrong_review(self):
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO mistakes (subject_id, question_type, question) "
                "VALUES (3, 'choice', '泰勒展开求极限')"
            )
            conn.execute(
                "INSERT INTO review_records (mistake_id, result, note, user_answer) "
                "VALUES (?, 'wrong', '忘了展开式', 'B')",
                (cur.lastrowid,),
            )
            conn.commit()
        finally:
            conn.close()

    def _cache_key(self):
        return f"weekly_report_{datetime.now().strftime('%Y-%m-%d')}"

    def test_empty_week_returns_empty_without_ai(self):
        # 用例按字母序执行，前面的用例可能已写入今天的缓存——先清掉再验"空周"路径
        conn = get_connection()
        try:
            conn.execute("DELETE FROM app_meta WHERE key = ?", (self._cache_key(),))
            conn.commit()
        finally:
            conn.close()
        with patch.object(ai_service, "analyze_weekly_report") as never:
            r = client.post("/api/ai/weekly-report")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["data"]["empty"])
        never.assert_not_called()

    def test_cached_report_returned_without_regenerating(self):
        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
                (self._cache_key(), json.dumps({"summary": "缓存版", "groups": []})),
            )
            conn.commit()
        finally:
            conn.close()
        with patch.object(
            ai_service, "analyze_weekly_report", side_effect=AssertionError("不应重烧 AI")
        ):
            r = client.post("/api/ai/weekly-report")
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertTrue(data["cached"])
        self.assertEqual(data["summary"], "缓存版")

    def test_force_regenerates_writes_cache_and_purges_old(self):
        self._seed_wrong_review()
        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO app_meta (key, value) VALUES ('weekly_report_2020-01-01', ?)",
                (json.dumps({"summary": "旧报"}),),
            )
            conn.commit()
        finally:
            conn.close()
        with patch.object(ai_service, "analyze_weekly_report", return_value={"summary": "新报"}):
            r = client.post("/api/ai/weekly-report", params={"force": 1})
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertFalse(data["cached"])
        self.assertEqual(data["summary"], "新报")
        self.assertEqual(data["week_count"], 1)

        conn = get_connection()
        try:
            keys = {
                row["key"]
                for row in conn.execute("SELECT key FROM app_meta WHERE key LIKE 'weekly_report_%'")
            }
        finally:
            conn.close()
        self.assertIn(self._cache_key(), keys)
        self.assertNotIn("weekly_report_2020-01-01", keys)


class SingleDeleteSnapshotTest(unittest.TestCase):
    """单题删除打 before-delete 快照（与批量删除对称）；404 不烧快照名额。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def _create_mistake(self):
        r = client.post(
            "/api/mistakes",
            json={
                "subject_id": 3,
                "question_type": "choice",
                "question": "单删快照测试题",
                "correct_answer": "A",
                "difficulty": 3,
                "difficulty_points": "测试难点",
                "analysis": "解析",
            },
        )
        assert r.status_code == 200, r.text
        return r.json()["data"]["id"]

    def test_delete_creates_snapshot_and_404_does_not(self):
        mid = self._create_mistake()
        before = len(list(settings.BACKUP_DIR.glob("*before-delete*.db")))
        r = client.delete(f"/api/mistakes/{mid}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("删除成功", r.json()["message"])
        after = list(settings.BACKUP_DIR.glob("*before-delete*.db"))
        self.assertEqual(len(after), before + 1)

        # 404：不存在也不该烧快照名额
        before2 = len(list(settings.BACKUP_DIR.glob("*before-delete*.db")))
        self.assertEqual(client.delete("/api/mistakes/999999").status_code, 404)
        self.assertEqual(len(list(settings.BACKUP_DIR.glob("*before-delete*.db"))), before2)


class ImageResolutionLimitTest(unittest.TestCase):
    """分辨率上限：正常小图放行，超总像素数拒绝（防绕过前端直灌的畸形大图）。"""

    @classmethod
    def setUpClass(cls):
        try:
            import PIL  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest("Pillow 未安装（CI 环境）") from exc
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def _png_bytes(self, w, h):
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (w, h), (200, 30, 30)).save(buf, "PNG")
        return buf.getvalue()

    def test_normal_image_passes_and_huge_is_rejected(self):
        from unittest.mock import patch

        from app.services import mistake_service

        ok_img = self._png_bytes(120, 90)
        self.assertTrue(mistake_service._save_image_data(ok_img).startswith("images/"))

        huge = self._png_bytes(300, 300)
        with patch.object(mistake_service, "IMAGE_MAX_PIXELS", 100):
            with self.assertRaises(ValueError) as ctx:
                mistake_service._save_image_data(huge)
            self.assertIn("分辨率过大", str(ctx.exception))


class EssayTrendTest(unittest.TestCase):
    """/essays/trend：全量时间正序 + 得分率换算正确。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO essay_records (kind, prompt_text, essay_text, score, max_score) "
                "VALUES ('e2_long','趋势甲','essay a',8,10)"
            )
            conn.execute(
                "INSERT INTO essay_records (kind, prompt_text, essay_text, score, max_score) "
                "VALUES ('e1_short','趋势乙','essay b',9,15)"
            )
            conn.commit()
        finally:
            conn.close()

    def test_trend_is_time_ascending_with_pct(self):
        r = client.get("/api/essays/trend")
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertGreaterEqual(len(data), 2)
        ids = [row["id"] for row in data]
        self.assertEqual(ids, sorted(ids))  # 时间正序
        for row in data:
            self.assertEqual(row["pct"], round((row["score"] or 0) / (row["max_score"] or 1) * 100))
        target = next(r for r in data if r["kind"] == "e2_long" and r["score"] == 8)
        self.assertEqual(target["pct"], 80)


class WeakPracticeTest(unittest.TestCase):
    """弱项组卷：从错得最多的知识点里抽题；没有错题时返回空。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def _add_mistake(self, question, tags, wrong_count=0):
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO mistakes (subject_id, question_type, question, correct_answer, "
                "difficulty, difficulty_points, analysis, wrong_count) "
                "VALUES (3,'choice',?,'A',3,'难点','解析',?)",
                (question, wrong_count),
            )
            mid = cur.lastrowid
            for tag in tags:
                conn.execute(
                    "INSERT INTO mistake_tag_map (mistake_id, tag) VALUES (?, ?)", (mid, tag)
                )
            conn.commit()
            return mid
        finally:
            conn.close()

    def test_weak_mode_selects_from_top_wrong_tags(self):
        self._add_mistake("泰勒展开题", ["泰勒公式"], wrong_count=5)
        self._add_mistake("级数题", ["级数"], wrong_count=3)
        self._add_mistake("无错题", ["没错过"])
        r = client.get("/api/reviews/practice", params={"mode": "weak", "count": 10})
        self.assertEqual(r.status_code, 200)
        questions = {i["question"] for i in r.json()["data"]}
        self.assertIn("泰勒展开题", questions)
        self.assertIn("级数题", questions)
        self.assertNotIn("无错题", questions)

    def test_weak_mode_empty_when_no_wrong(self):
        self._add_mistake("只对不错的题", ["稳定发挥"], wrong_count=0)
        r = client.get("/api/reviews/practice", params={"mode": "weak", "count": 10})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"], [])


class ImagesSnapshotTest(unittest.TestCase):
    """图片目录打包备份：zip 生成、缩略图不打包、超份数自动轮换。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def test_zip_created_and_rotated(self):
        import zipfile

        from app.database import snapshot_images

        img_dir = settings.DB_PATH.parent / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / "a.png").write_bytes(b"x")
        (img_dir / "_thumbs").mkdir()
        (img_dir / "_thumbs" / "t.webp").write_bytes(b"y")

        name = snapshot_images()
        self.assertTrue(name and name.startswith("images_backup_"))
        with zipfile.ZipFile(settings.BACKUP_DIR / name) as zf:
            names = zf.namelist()
        self.assertIn("a.png", names)
        self.assertNotIn("_thumbs/t.webp", names)  # 缩略图可再生，不打包

        for _ in range(6):
            snapshot_images()
        self.assertLessEqual(len(list(settings.BACKUP_DIR.glob("images_backup_*.zip"))), 5)


class VariantEndpointTest(unittest.TestCase):
    """AI 举一反三端点：结果透传、404 不触发 AI、错题不存在不烧额度。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def _create_mistake(self):
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO mistakes (subject_id, question_type, question, correct_answer, "
                "difficulty, difficulty_points, analysis) "
                "VALUES (3,'choice','变式原题',  'A',3,'难点','原题解析')"
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def test_variant_returns_generated_result(self):
        from app.services import ai_service as ai_mod

        mid = self._create_mistake()
        fake = {
            "question": "变式后的新题干",
            "option_a": "1",
            "option_b": "2",
            "option_c": "3",
            "option_d": "4",
            "answer": "B",
            "analysis": "变式解析",
            "focus": "同考点不同情境",
        }
        with patch.object(ai_mod, "generate_variant", return_value=fake) as gen:
            r = client.post("/api/ai/variant", json={"mistake_id": mid})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["data"]["question"], "变式后的新题干")
        self.assertEqual(r.json()["data"]["answer"], "B")
        gen.assert_called_once()

    def test_variant_404_without_ai_call(self):
        from app.services import ai_service as ai_mod

        with patch.object(
            ai_mod,
            "generate_variant",
            side_effect=AssertionError("404 时不应调 AI"),
        ):
            r = client.post("/api/ai/variant", json={"mistake_id": 999999})
        self.assertEqual(r.status_code, 404)


class ErrorReasonPersistenceTest(unittest.TestCase):
    """error_reason 数据链路：CREATE 带、PUT 不带键保留、显式空串清除、导出带回。

    这是个"普通字段不传即重置"陷阱的反例——归因表单不在编辑表单里，
    必须走 ATTACHMENT_KEYS 的"不带键=保留"语义，否则编辑一次归因就被洗掉。
    """

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    @staticmethod
    def _payload(question="归因链路测试题", error_reason=None):
        payload = {
            "subject_id": 3,
            "question_type": "choice",
            "question": question,
            "correct_answer": "A",
            "difficulty": 3,
            "difficulty_points": "难点",
            "analysis": "解析",
        }
        if error_reason is not None:
            payload["error_reason"] = error_reason
        return payload

    def _detail(self, mid):
        return client.get(f"/api/mistakes/{mid}").json()["data"]

    def test_create_put_preserves_clear_and_export(self):
        r = client.post("/api/mistakes", json=self._payload(error_reason="knowledge"))
        self.assertEqual(r.status_code, 200, r.text)
        mid = r.json()["data"]["id"]
        self.assertEqual(self._detail(mid)["error_reason"], "knowledge")

        # PUT 全量更新但**不带** error_reason 键 → 保留（表单没有这个输入框）
        put_payload = self._payload(question="改过题干的题")
        r2 = client.put(f"/api/mistakes/{mid}", json=put_payload)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(self._detail(mid)["error_reason"], "knowledge")

        # 显式提交空串 = 真的要清除
        r3 = client.put(f"/api/mistakes/{mid}", json=self._payload(error_reason=""))
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(self._detail(mid)["error_reason"], "")

        # 导出必须带回归因（导入走 MISTAKE_COLUMNS 重建，同列清单）
        client.post("/api/mistakes", json=self._payload(question="带归因的题", error_reason="calc"))
        exported = client.get("/api/export").json()["data"]["mistakes"]
        target = next(m for m in exported if m["question"] == "带归因的题")
        self.assertEqual(target.get("error_reason"), "calc")


class ImportScheduleRoundtripTest(unittest.TestCase):
    """导出→导入往返：SM-2 调度字段/星标/归因必须保真（复习进度是用户资产）。

    此前导入按内容列重建行，ease_factor/复习次数/下次复习时间被静默清零。
    """

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def test_export_import_preserves_schedule(self):
        r = client.post(
            "/api/mistakes",
            json={
                "subject_id": 3,
                "question_type": "choice",
                "question": "调度往返测试题目验证",
                "correct_answer": "A",
                "difficulty": 3,
                "difficulty_points": "难点",
                "analysis": "解析",
                "review_count": 5,
                "wrong_count": 2,
                "mastery_level": 3,
                "ease_factor": 2.7,
                "last_interval": 7,
                "next_review_at": "2099-01-01 00:00:00",
                "review_paused": True,
                "starred": True,
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        mid = r.json()["data"]["id"]

        exported = client.get("/api/export").json()["data"]
        imported = client.post("/api/import", json=exported).json()["data"]
        self.assertEqual(imported["failed"], [])
        # 全部撞指纹去重（原题还在库里）→ 没有新建行；真往返要换库验证，
        # 这里直接验证**导出形状**带了调度字段 + build 后字段不归零即可：
        exported_row = next(m for m in exported["mistakes"] if m["id"] == mid)
        self.assertEqual(exported_row["ease_factor"], 2.7)
        self.assertEqual(exported_row["review_count"], 5)
        self.assertEqual(exported_row["starred"], 1)
        self.assertEqual(exported_row["next_review_at"], "2099-01-01 00:00:00")
        # 原库里的行也没被导入流程动过
        detail = client.get(f"/api/mistakes/{mid}").json()["data"]
        self.assertEqual(detail["ease_factor"], 2.7)
        self.assertEqual(detail["review_count"], 5)

    def test_import_carries_schedule_into_new_row(self):
        """换库语义：同一份导出在删掉原题后重导，调度字段原样落地（手动新录才走默认值）。"""
        exported = client.get("/api/export").json()["data"]
        target = next(m for m in exported["mistakes"] if m["question"] == "调度往返测试题目验证")
        client.delete(f"/api/mistakes/{target['id']}")
        # 只导这一条，避免种子演示数据干扰计数
        r = client.post("/api/import", json={"mistakes": [target]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["data"]["created"], 1)
        # 列表列不含调度字段，详情接口再取一次
        rows = client.get("/api/mistakes", params={"search": "调度往返测试题目验证"}).json()["data"]
        self.assertEqual(len(rows), 1)
        detail = client.get(f"/api/mistakes/{rows[0]['id']}").json()["data"]
        self.assertEqual(detail["ease_factor"], 2.7)
        self.assertEqual(detail["review_count"], 5)
        self.assertEqual(detail["starred"], 1)
        self.assertEqual(detail["next_review_at"], "2099-01-01 00:00:00")


if __name__ == "__main__":
    unittest.main()
