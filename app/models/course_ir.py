from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TaughtStatus(str, Enum):
    ORAL = "oral"
    SUPPORT_ONLY = "support_only"
    BOTH = "both"
    UNCERTAIN = "uncertain"


class AuditCategory(str, Enum):
    RESOLVED = "resolved"
    CERTAIN_ERROR = "certain_error"
    PROBABLE = "probable"
    LITERATURE_DEVIATION = "literature_deviation"
    UNCERTAIN = "uncertain"
    OMISSION = "omission"


class SourceType(str, Enum):
    AUDIO = "audio"
    SYLLABUS = "syllabus"
    SUPPORT = "support"


class SourceRef(BaseModel):
    type: SourceType
    ref: str
    excerpt: str


class CorrectionRef(BaseModel):
    original: str
    proposed: str
    confidence: float = 0.0
    evidence: str = ""
    status: str = "pending"
    verdict: str = ""


class CourseItem(BaseModel):
    id: str
    text: str
    section: str = ""
    taught_status: TaughtStatus = TaughtStatus.UNCERTAIN
    sources: list[SourceRef] = Field(default_factory=list)
    audit_category: AuditCategory | None = None
    priority: Literal["fort", "moyen", "faible"] | None = None
    corrections: list[CorrectionRef] = Field(default_factory=list)


class AuditSection(BaseModel):
    title: str
    category: AuditCategory
    rows: list[dict] = Field(default_factory=list)


class CourseIR(BaseModel):
    subject: str
    session_date: str
    items: list[CourseItem] = Field(default_factory=list)
    audit_sections: list[AuditSection] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
