from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests


DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"


class PublicWebSearchError(RuntimeError):
    pass


@dataclass
class PublicWebSearchClient:
    session: Any = requests
    timeout: int = 15

    def search(self, query: str, *, max_results: int = 4) -> dict[str, Any]:
        clean_query = " ".join(str(query or "").split())
        if not clean_query:
            return {"used": False, "reason": "empty_query", "results": [], "count": 0}
        attempted_queries = expand_public_web_query(clean_query)
        last_results: list[dict[str, Any]] = []
        try:
            for attempted in attempted_queries:
                response = self.session.get(
                    DUCKDUCKGO_HTML_URL,
                    params={"q": attempted},
                    timeout=self.timeout,
                    headers={"User-Agent": "VeritasLegal/1.0 public-web-research"},
                )
                response.raise_for_status()
                last_results = parse_duckduckgo_html(response.text, max_results=max_results)
                if last_results:
                    break
        except Exception as exc:
            raise PublicWebSearchError(f"Public web search failed: {exc}") from exc
        if not last_results:
            last_results = ccr_source_fallbacks(clean_query, session=self.session, timeout=self.timeout)
        return {
            "used": bool(last_results),
            "reason": "public_web_search" if last_results else "no_public_web_results",
            "query": clean_query,
            "attempted_queries": attempted_queries,
            "count": len(last_results),
            "results": last_results,
            "source_class": "public_web_search",
            "provider": "DuckDuckGo HTML",
            "warnings": [
                {
                    "code": "public_web_verification_required",
                    "message": "Public web search results may be incomplete or stale; verify primary sources before legal reliance.",
                }
            ],
        }


def expand_public_web_query(query: str) -> list[str]:
    clean = " ".join(str(query or "").split())
    queries = [clean]
    ccr_match = re.search(r"\bccr\s*[-§]?\s*(\d{3,5}(?:-\d+)?)\b", clean, flags=re.I)
    if ccr_match:
        section = ccr_match.group(1)
        queries.extend(
            [
                f"CCR {section} California Code of Regulations",
                f"14 CCR {section}",
                f"California Code of Regulations section {section}",
            ]
        )
    for value in list(queries):
        if value not in queries:
            queries.append(value)
    return list(dict.fromkeys(queries))


def ccr_source_fallbacks(query: str, *, session: Any = requests, timeout: int = 15) -> list[dict[str, Any]]:
    ccr_match = re.search(r"\bccr\s*[-§]?\s*(\d{3,5}(?:-\d+)?)\b", query, flags=re.I)
    if not ccr_match:
        return []
    section = ccr_match.group(1)
    candidates = [
        (
            "Cornell Legal Information Institute",
            f"https://www.law.cornell.edu/regulations/california/14-CCR-{section}",
        ),
        (
            "Justia Regulations",
            f"https://regulations.justia.com/states/california/title-14/division-3/chapter-1/section-{section}/",
        ),
        (
            "California Code of Regulations",
            "https://govt.westlaw.com/calregs/Index?transitionType=Default&contextData=%28sc.Default%29",
        ),
    ]
    results: list[dict[str, Any]] = []
    for provider, url in candidates:
        title = f"14 CCR § {section}"
        snippet = "Public source lead for California Code of Regulations research. Open and verify the source before legal reliance."
        try:
            response = session.get(url, timeout=timeout, headers={"User-Agent": "VeritasLegal/1.0 public-web-research"})
            if int(getattr(response, "status_code", 0) or 0) >= 400:
                if provider != "California Code of Regulations":
                    continue
            text = getattr(response, "text", "") or ""
            title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
            if title_match:
                title = clean_html(title_match.group(1))
            snippet_match = re.search(r"<p[^>]*>(.*?)</p>", text, flags=re.I | re.S)
            if snippet_match:
                snippet = clean_html(snippet_match.group(1))
        except Exception:
            if provider != "California Code of Regulations":
                continue
        results.append(
            {
                "title": title,
                "snippet": snippet,
                "source_url": url,
                "source_class": "public_web_search",
                "source_provider": provider,
                "citation": f"14 CCR § {section}",
                "text": snippet,
            }
        )
    return results


def parse_duckduckgo_html(raw_html: str, *, max_results: int = 4) -> list[dict[str, Any]]:
    text = str(raw_html or "")
    blocks = re.findall(r'<div class="result(?: results_links_deep)?[^"]*"[^>]*>(.*?)</div>\s*</div>', text, flags=re.I | re.S)
    if not blocks:
        blocks = re.split(r'<div class="result', text, flags=re.I)[1:]
    results: list[dict[str, Any]] = []
    for block in blocks:
        link_match = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.I | re.S)
        if not link_match:
            continue
        raw_url = html.unescape(link_match.group(1))
        title = clean_html(link_match.group(2))
        snippet_match = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>', block, flags=re.I | re.S)
        snippet = clean_html((snippet_match.group(1) or snippet_match.group(2)) if snippet_match else "")
        url = normalize_duckduckgo_url(raw_url)
        if not title or not url:
            continue
        results.append(
            {
                "title": title,
                "snippet": snippet,
                "source_url": url,
                "source_class": "public_web_search",
                "source_provider": "DuckDuckGo HTML",
                "citation": title,
                "text": snippet,
            }
        )
        if len(results) >= max(1, max_results):
            break
    return results


def normalize_duckduckgo_url(raw_url: str) -> str:
    value = html.unescape(str(raw_url or ""))
    if value.startswith("//"):
        value = "https:" + value
    parsed = urlparse(value)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return value


def clean_html(value: str) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()
