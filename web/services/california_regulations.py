from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Optional

import requests


JUSTIA_CCR_BASE = "https://regulations.justia.com/states/california"
OFFICIAL_CCR_INDEX = "https://govt.westlaw.com/calregs/Index?transitionType=Default&contextData=%28sc.Default%29"


class CaliforniaRegulationsError(RuntimeError):
    pass


@dataclass
class CaliforniaRegulationsClient:
    session: Any = requests
    timeout: int = 15

    def lookup(self, query: str) -> dict[str, Any]:
        parsed = parse_ccr_reference(query)
        if not parsed:
            return {"used": False, "reason": "no_ccr_reference", "results": [], "count": 0}

        title = parsed.get("title") or "14"
        section = parsed["section"]
        url = ccr_section_url(title=title, section=section)
        try:
            response = self.session.get(url, timeout=self.timeout, headers={"User-Agent": "VeritasLegal/1.0 legal-research"})
            response.raise_for_status()
        except Exception as exc:
            raise CaliforniaRegulationsError(f"California regulation lookup failed: {exc}") from exc

        result = parse_justia_ccr_page(response.text, source_url=url, title=title, section=section)
        if not result:
            return {
                "used": False,
                "reason": "no_public_regulation_match",
                "results": [],
                "count": 0,
                "query": query,
                "source_class": "california_public_regulation",
            }
        return {
            "used": True,
            "reason": "california_regulation_lookup",
            "query": query,
            "count": 1,
            "results": [result],
            "source_class": "california_public_regulation",
            "warnings": [
                {
                    "code": "verify_official_ccr",
                    "message": "Justia provides a public regulation page but warns it may not be current. Verify against the official California Code of Regulations source when relying on it.",
                }
            ],
            "official_index_url": OFFICIAL_CCR_INDEX,
        }


def parse_ccr_reference(query: str) -> Optional[dict[str, str]]:
    text = " ".join(str(query or "").split())
    if not text:
        return None
    title_match = re.search(r"\btitle\s+(\d{1,2})\b", text, flags=re.I)
    explicit_title = re.search(r"\b(\d{1,2})\s*(?:ccr|c\.?\s*c\.?\s*r\.?|ca\s+code\s+regs?)\b", text, flags=re.I)
    section_match = re.search(r"(?:ccr|c\.?\s*c\.?\s*r\.?|section|§)\s*[-§\s]*(\d{3,5}(?:-\d+)?)\b", text, flags=re.I)
    if not section_match:
        section_match = re.search(r"\b(\d{3,5}(?:-\d+)?)\b", text) if re.search(r"\bccr\b|c\.?\s*c\.?\s*r\.?", text, flags=re.I) else None
    if not section_match:
        return None
    return {
        "title": (title_match or explicit_title).group(1) if (title_match or explicit_title) else "",
        "section": section_match.group(1),
    }


def ccr_section_url(*, title: str, section: str) -> str:
    title_slug = str(title).strip()
    section_slug = str(section).strip().lower()
    if title_slug == "14":
        return f"{JUSTIA_CCR_BASE}/title-14/division-3/chapter-1/section-{section_slug}/"
    return f"{JUSTIA_CCR_BASE}/title-{title_slug}/section-{section_slug}/"


def parse_justia_ccr_page(raw_html: str, *, source_url: str, title: str, section: str) -> Optional[dict[str, Any]]:
    text = html.unescape(str(raw_html or ""))
    heading_match = re.search(r"<h1[^>]*>\s*California Code of Regulations\s*</h1>.*?Section\s+" + re.escape(section) + r"\s*-\s*([^<\n]+)", text, flags=re.I | re.S)
    title_match = re.search(r"Title\s+" + re.escape(title) + r"\s*-\s*([^<\n]+)", text, flags=re.I)
    current_match = re.search(r"Current through\s+([^<\n]+)", text, flags=re.I)
    body_match = re.search(r"Current through[^<]*</?[^>]*>\s*(?:\n|\r|\s)*([^<]{40,2000})", text, flags=re.I)
    if not body_match:
        body_match = re.search(r"<p[^>]*>\s*(No person shall[^<]+)</p>", text, flags=re.I)
    body = clean_text(body_match.group(1) if body_match else "")
    if not body:
        return None
    section_name = clean_text(heading_match.group(1) if heading_match else "")
    title_name = clean_text(title_match.group(1) if title_match else "")
    currentness = clean_text(current_match.group(1) if current_match else "")
    return {
        "title": f"{title} CCR § {section}" + (f" - {section_name}" if section_name else ""),
        "citation": f"{title} CCR § {section}",
        "jurisdiction": "California",
        "source_class": "california_public_regulation",
        "source_provider": "Justia Regulations",
        "source_url": source_url,
        "official_index_url": OFFICIAL_CCR_INDEX,
        "currentness": currentness,
        "title_name": title_name,
        "section_name": section_name,
        "text": body,
        "snippet": body[:500],
        "source_ids": {"title": title, "section": section},
        "warnings": [
            "Verify currentness against the official California Code of Regulations source before filing or relying on the text."
        ],
    }


def clean_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", without_tags).strip()
