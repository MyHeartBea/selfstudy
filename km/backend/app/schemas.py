"""Pydantic 请求与响应模型，用于接口文档和基础校验。"""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 200
    data: Any = None
    message: str = "success"


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


class MistakeUpdate(MistakeCreate):
    """更新错题。注意：PUT 为全量覆盖语义（所有必填字段须同时提交），
    前端 MistakeForm 提交完整表单；如需局部更新请改用 PATCH。"""

    pass


class KnowledgeUpdate(BaseModel):
    summary: str = ""
    subject_id: Optional[int] = None
    sub_subject_id: Optional[int] = None
    related_tags: List[str] = []


class ImportPayload(BaseModel):
    mistakes: List[MistakeCreate] = Field(min_length=1, max_length=5000)


class ReviewCreate(BaseModel):
    result: bool
    note: str = ""
    user_answer: str = ""


class AiAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)


class AiOcrRequest(BaseModel):
    image_base64: str = Field(min_length=1, max_length=20000000)


class AiSummarizeRequest(BaseModel):
    tag_name: str = Field(min_length=1)


class JudgeRequest(BaseModel):
    user_answer: str = Field(min_length=1)


class GradeRequest(BaseModel):
    user_answer: str = Field(min_length=1)


class SubjectProfileUpdate(BaseModel):
    focus_areas: List[str] = []
    review_tips: str = ""


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
