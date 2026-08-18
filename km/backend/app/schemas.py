"""Pydantic 请求与响应模型，用于接口文档和基础校验。"""

from typing import List, Optional

from pydantic import BaseModel, Field


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


class ReviewCreate(BaseModel):
    result: bool
    note: str = ""
    user_answer: str = ""


class AiAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
    # 可选：补充解题要求/思路（例如"按配方法求解，正交变换步骤写详细"）
    instruction: str = Field(default="", max_length=5000)


class AiOcrRequest(BaseModel):
    image_base64: str = Field(min_length=1, max_length=20000000)
    # 可选：补充解题要求/思路，AI 解析时须遵循
    instruction: str = Field(default="", max_length=5000)
    # 可选：参考图片（按图中思路/方法解题）
    reference_image_base64: str = Field(default="", max_length=20000000)


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
