"""Pydantic 请求与响应模型，用于接口文档和基础校验。"""

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class MistakeCreate(BaseModel):
    subject_id: int
    sub_subject_id: Optional[int] = None
    question_type: str = "choice"
    question: str = Field(min_length=1)
    option_a: str = ""
    option_b: str = ""
    option_c: str = ""
    option_d: str = ""
    correct_answer: str = ""
    answer_aliases: List[str] = []
    analysis: str = ""
    difficulty: int = Field(ge=1, le=5)
    difficulty_points: str = ""
    knowledge_tags: List[str] = []
    approach: str = ""
    source: str = ""
    source_type: str = "other"
    source_year: str = ""
    source_name: str = ""
    # 题干配图：元素为 data URL（新上传）或已保存的相对路径（编辑时保留）
    images: List[str] = Field(default_factory=list, max_length=5)
    # 英语整篇精读（可选）：解析后挂在错题上的附加内容
    passage_text: str = ""
    passage_translation: str = ""
    english_sentences: List[dict] = Field(default_factory=list)
    english_phrases: List[dict] = Field(default_factory=list)
    english_words: List[dict] = Field(default_factory=list)
    english_questions: List[dict] = Field(default_factory=list)


class MistakeUpdate(MistakeCreate):
    """更新错题。PUT 为全量覆盖语义：提交了 `"passage_text": ""` 就是清空。

    例外是 images 与 passage_text / passage_translation / english_* 这组"附加内容"键
    （见 mistake_service.ATTACHMENT_KEYS）：**压根不带这些键**时服务层会按库里原值回填，
    因为它们是 AI 整篇精读的唯一副本，被一个只含基础字段的表单覆盖掉就无法恢复。
    前端 MistakeForm 始终提交完整字段，所以行为不变；如需局部更新请改用 PATCH。
    """

    pass


class KnowledgeUpdate(BaseModel):
    """知识点更新（PATCH 语义）：字段为 None 表示不修改，避免空 body 静默清空。"""

    summary: Optional[str] = None
    subject_id: Optional[int] = None
    sub_subject_id: Optional[int] = None
    related_tags: Optional[List[str]] = None


class KnowledgeCreate(BaseModel):
    """手动创建知识点词条。"""

    tag_name: str = Field(min_length=1, max_length=100)
    subject_id: Optional[int] = None
    sub_subject_id: Optional[int] = None
    summary: str = ""
    related_tags: List[str] = []


class ImportPayload(BaseModel):
    mistakes: List[MistakeCreate] = Field(min_length=1, max_length=5000)


class PaperCreate(BaseModel):
    subject: str = ""
    year: str = ""
    title: str = ""
    source_path: str
    answer_path: str = ""


class PaperAnswerPatch(BaseModel):
    correct_answer: str = ""


class MockCreate(BaseModel):
    exam_year: str = ""
    total: int = 0
    correct: int = 0
    score: int = 0
    duration_min: int = 60
    used_seconds: int = 0


class ReviewCreate(BaseModel):
    result: bool
    note: str = ""
    user_answer: str = ""


class AiAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
    # 可选：补充解题要求/思路（例如"按配方法求解，正交变换步骤写详细"）
    instruction: str = Field(default="", max_length=5000)


class AiOcrRequest(BaseModel):
    image_base64: str = Field(default="", max_length=20000000)
    # 可选：多图（知识点粘贴多张截图时一次提交；按顺序逐张提文字后合并）
    images: List[str] = Field(default_factory=list, max_length=10)
    # 可选：补充解题要求/思路，AI 解析时须遵循
    instruction: str = Field(default="", max_length=5000)
    # 可选：参考图片（按图中思路/方法解题）
    reference_image_base64: str = Field(default="", max_length=20000000)

    @model_validator(mode="after")
    def _require_at_least_one_image(self):
        """image_base64 与 images 至少给一个，否则后续识别必然空跑。"""
        if not self.image_base64.strip() and not any(str(i).strip() for i in self.images):
            raise ValueError("image_base64 与 images 至少需要提供一个")
        return self


class AiEnglishRequest(BaseModel):
    """英语整篇精读：支持多张图片（原文段落 + 选项）与可选粘贴文本。"""

    images: List[str] = Field(default_factory=list, max_length=10)
    text: str = Field(default="", max_length=50000)
    # 可选：补充指令（如「逐句翻译」「重点讲解长难句」）
    instruction: str = Field(default="", max_length=5000)


class AiEssayRequest(BaseModel):
    """英语作文批改：图片（手写稿拍照，先原样转录）或直接粘贴作文文本。"""

    images: List[str] = Field(default_factory=list, max_length=10)
    image_base64: str = Field(default="", max_length=20000000)
    text: str = Field(default="", max_length=50000)
    # 作文类型：e1_short / e1_long / e2_short / e2_long
    kind: str = Field(default="e2_long", max_length=20)
    # 作文题目/要求（可选，提供后按要点覆盖度批改）
    prompt_text: str = Field(default="", max_length=10000)
    instruction: str = Field(default="", max_length=5000)
    # 是否存档到作文记录（默认存）
    persist: bool = True


class JudgeRequest(BaseModel):
    user_answer: str = Field(min_length=1)


class GradeRequest(BaseModel):
    user_answer: str = Field(min_length=1)


class SubjectProfileUpdate(BaseModel):
    """科目档案更新（PATCH 语义）：字段为 None 表示不修改。"""

    focus_areas: Optional[List[str]] = None
    review_tips: Optional[str] = None


class SourceTypeUpdate(BaseModel):
    source_type: str = "other"
    source_year: str = ""
    source_name: str = ""


class StarRequest(BaseModel):
    """收藏标星：不传 starred 时为切换（toggle）。"""

    starred: Optional[bool] = None


class QuotaUpdate(BaseModel):
    """每日复习配额覆盖值：0 = 不限。"""

    daily_limit: int = Field(ge=0, le=1000)


class SnoozeRequest(BaseModel):
    """「稍后再看」：把这道题推到明天再看，每天限 3 次。"""

    mistake_id: int


class FormulaCreate(BaseModel):
    category: str = "高等数学"
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)


class FormulaUpdate(FormulaCreate):
    pass


class BatchMistakeRequest(BaseModel):
    ids: List[int] = Field(min_length=1)
    action: str
    source_type: str = "other"
    source_year: str = ""
    source_name: str = ""


class VocabCreate(BaseModel):
    """新增生词。"""

    word: str = Field(min_length=1, max_length=80)
    meaning: str = Field(default="", max_length=2000)
    phonetic: str = Field(default="", max_length=120)
    example: str = Field(default="", max_length=2000)
    note: str = Field(default="", max_length=2000)
    source: str = Field(default="", max_length=200)
    kind: str = Field(default="word", max_length=20)


class VocabUpdate(BaseModel):
    """更新生词（PATCH 语义：None 字段保持不变）。"""

    word: Optional[str] = Field(default=None, max_length=80)
    meaning: Optional[str] = Field(default=None, max_length=2000)
    phonetic: Optional[str] = Field(default=None, max_length=120)
    example: Optional[str] = Field(default=None, max_length=2000)
    note: Optional[str] = Field(default=None, max_length=2000)
    source: Optional[str] = Field(default=None, max_length=200)


class VocabReview(BaseModel):
    """闪卡复习结果：known=认识 fuzzy=模糊 unknown=不认识。"""

    result: str


class SnapshotRestore(BaseModel):
    """整库回滚到某份快照。`confirm` 必须与 `name` 一字不差。

    为什么要在服务端也要一份确认：这个请求一旦发出就是覆盖全部数据。
    只靠前端"输入名字才让点按钮"的话，任何一次前端漏改/绕过都会把
    一个不可逆操作变成一次普通点击。
    """

    name: str = Field(min_length=1, max_length=120)
    confirm: str = Field(default="", max_length=120)
