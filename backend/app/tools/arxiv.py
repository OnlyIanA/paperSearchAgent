from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import httpx

from app.core.config import Settings
from app.models.schemas import Paper
from app.tools.cache import TTLCache


ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _to_search_query(query: str) -> str:
    query = query.strip()
    if re.match(r"^(all|ti|au|abs|cat|id|jr|co|rn):", query, flags=re.IGNORECASE):
        return query
    return f"all:{query}"


class ArxivSearchTool:
    """arXiv Atom API client used by both agent tools and MCP server."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache: TTLCache[list[Paper]] = TTLCache(settings.cache_ttl_seconds)

    async def search(self, query: str, max_results: int | None = None) -> list[Paper]:
        max_results = max_results or self.settings.arxiv_default_max_results
        cache_key = f"{query.strip().lower()}::{max_results}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "search_query": _to_search_query(query),
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        headers = {"User-Agent": "paper-search-agent/0.1 (research assistant)"}
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(self.settings.arxiv_api_url, params=params, headers=headers)
            response.raise_for_status()

        papers = self._parse_response(response.text)
        self.cache.set(cache_key, papers)
        return papers

    def _parse_response(self, xml_text: str) -> list[Paper]:
        root = ET.fromstring(xml_text)
        papers: list[Paper] = []
        for entry in root.findall("atom:entry", ATOM_NS):
            source_url = _clean_text(entry.findtext("atom:id", default="", namespaces=ATOM_NS))
            arxiv_id = source_url.rstrip("/").split("/")[-1]
            title = _clean_text(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
            abstract = _clean_text(entry.findtext("atom:summary", default="", namespaces=ATOM_NS))
            authors = [
                _clean_text(author.findtext("atom:name", default="", namespaces=ATOM_NS))
                for author in entry.findall("atom:author", ATOM_NS)
            ]
            authors = [author for author in authors if author]
            categories = [
                category.attrib.get("term", "")
                for category in entry.findall("atom:category", ATOM_NS)
                if category.attrib.get("term")
            ]
            pdf_url = ""
            for link in entry.findall("atom:link", ATOM_NS):
                if link.attrib.get("type") == "application/pdf":
                    pdf_url = link.attrib.get("href", "")
                    break
            if not pdf_url and arxiv_id:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

            papers.append(
                Paper(
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    pdf_url=pdf_url,
                    source_url=source_url,
                    published=_clean_text(
                        entry.findtext("atom:published", default="", namespaces=ATOM_NS)
                    )
                    or None,
                    updated=_clean_text(entry.findtext("atom:updated", default="", namespaces=ATOM_NS))
                    or None,
                    categories=categories,
                )
            )
        return papers

