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
    firm_profile_id: Optional[str] = None
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
    prepared_by_id: Optional[str] = None
    reviewed_by_id: Optional[str] = None
    approved_by_id: Optional[str] = None
    signed_by_id: Optional[str] = None
    filed_by_id: Optional[str] = None


class FirmProfileRequest(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    office_name: Optional[str] = None
    office_address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    confidentiality_notice: Optional[str] = None
    default_footer: Optional[str] = None
    default_fonts: Optional[Dict[str, Any]] = None
    margins: Optional[Dict[str, Any]] = None
    pleading_paper_defaults: Optional[Dict[str, Any]] = None
    preferred_document_styles: Optional[list[str]] = None
    court_specific_templates: Optional[Dict[str, Any]] = None
    billing_contact: Optional[Dict[str, Any]] = None
    branding_profile: Optional[Dict[str, Any]] = None
    multiple_offices: Optional[list[Dict[str, Any]]] = None
    notes: Optional[str] = None


class StaffDirectoryRequest(BaseModel):
    id: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "legal_assistant"
    bar_number: Optional[str] = None
    title: Optional[str] = None
    office: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    signature_block: Optional[str] = None
    initials: Optional[str] = None
    document_stamp: Optional[str] = None
    matters_accessible: Optional[list[str]] = None
    permissions: Optional[list[str]] = None
    active: Optional[bool] = True
    notes: Optional[str] = None


class AuthorityStampRequest(BaseModel):
    case_id: Optional[str] = None
    firm_profile_id: Optional[str] = None
    prepared_by_id: Optional[str] = None
    reviewed_by_id: Optional[str] = None
    approved_by_id: Optional[str] = None
    signed_by_id: Optional[str] = None
    filed_by_id: Optional[str] = None
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


class CourtListenerSearchRequest(BaseModel):
    query: str
    case_id: Optional[str] = None
    search_type: str = "o"
    page_size: int = 5
    semantic: bool = False


class CourtListenerCitationRequest(BaseModel):
    text: Optional[str] = None
    volume: Optional[str] = None
    reporter: Optional[str] = None
    page: Optional[str] = None
    case_id: Optional[str] = None


class CourtListenerLookupRequest(BaseModel):
    id: str
    case_id: Optional[str] = None


class CourtListenerIngestRequest(BaseModel):
    query: str
    case_id: Optional[str] = None
    case_title: Optional[str] = None
    search_type: str = "r"
    page_size: int = 3
    semantic: bool = False


class EdgarSearchRequest(BaseModel):
    query: str
    case_id: Optional[str] = None
    page_size: int = 10
    start: int = 0


class EdgarCompanyRequest(BaseModel):
    cik: str
    case_id: Optional[str] = None


class EdgarIngestRequest(BaseModel):
    query: Optional[str] = None
    cik: Optional[str] = None
    case_id: Optional[str] = None
    case_title: Optional[str] = None
    page_size: int = 3
    start: int = 0


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
