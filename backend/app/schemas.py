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
    """更新错题。注意：PUT 为全量覆盖语义（所有必填字段须同时提交），
    前端 MistakeForm 提交完整表单；如需局部更新请改用 PATCH。"""

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
    subject: str = ''
    year: str = ''
    title: str = ''
    source_path: str
    answer_path: str = ''


class MockCreate(BaseModel):
    exam_year: str = ''
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
