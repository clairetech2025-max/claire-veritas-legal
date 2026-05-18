from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    case_id: Optional[str] = None
    mode: str = "legal"
    top_k: int = 8
    temperature: float = 0.2
    max_tokens: int = 700


class SearchRequest(BaseModel):
    query: str
    case_id: Optional[str] = None
    top_k: int = 8


class TimelineRequest(BaseModel):
    case_id: Optional[str] = None
    limit: int = 100


class OCRRequest(BaseModel):
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    content_b64: Optional[str] = None


class LoadCorpusRequest(BaseModel):
    path: str
    case_id: Optional[str] = None


class IngestRequest(BaseModel):
    text: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    content_b64: Optional[str] = None
    case_id: Optional[str] = None
    case_title: Optional[str] = None
    source_type: str = "upload"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SuggestRequest(BaseModel):
    query: str
    case_id: Optional[str] = None
    top_k: int = 8


class GyroRequest(BaseModel):
    input: str
    case_id: Optional[str] = None
    top_k: int = 5
    ingest_input: bool = False


class PromptPrefixRequest(BaseModel):
    input: str
    system_instruction: str = "You are CLAIRE // VERITAS LEGAL."
    case_id: Optional[str] = None
    top_k: int = 5
    ingest_input: bool = False


class MatterRequest(BaseModel):
    case_id: Optional[str] = None
    title: Optional[str] = None
    court_profile_id: Optional[str] = None
    court_name: Optional[str] = None
    district: Optional[str] = None
    jurisdiction: Optional[str] = "Federal"
    matter_type: Optional[str] = "civil"
    practice_area: Optional[str] = None
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    counsel: Optional[str] = None
    billing_increment_minutes: Optional[int] = 15
    billing_rate: Optional[float] = 0.0
    confidentiality_level: Optional[str] = "Privileged"
    notes: Optional[str] = None


class CourtProfileRequest(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    scope: Optional[str] = None
    caption_notes: Optional[list[str]] = None
    motion_notes: Optional[list[str]] = None
    artifact_defaults: Optional[list[str]] = None
    local_rules_source: Optional[str] = None
    template_priority: Optional[list[str]] = None
    page_limit_hint: Optional[str] = None
    notes: Optional[str] = None


class CourtRulesLoadRequest(BaseModel):
    path: str


class DocketImportRequest(BaseModel):
    case_id: Optional[str] = None
    court_name: Optional[str] = None
    source_name: Optional[str] = None
    path: Optional[str] = None
    text: Optional[str] = None
    content_b64: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class DraftRequest(BaseModel):
    case_id: Optional[str] = None
    template_id: str = "case_theory_memo"
    query: str = ""


class ExportRequest(BaseModel):
    case_id: Optional[str] = None
    template_id: str = "case_theory_memo"
    query: str = ""
    format: str = "markdown"
    redact: bool = False


class AnalysisRequest(BaseModel):
    case_id: Optional[str] = None
    query: str = ""
    top_k: int = 10


class BillingRequest(BaseModel):
    case_id: Optional[str] = None
    billing_increment_minutes: Optional[int] = 15
    billing_rate: Optional[float] = 0.0
    task_description: Optional[str] = ""
