from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    case_id: Optional[str] = None
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

