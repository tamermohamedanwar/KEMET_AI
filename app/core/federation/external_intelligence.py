from __future__ import annotations

from dataclasses import dataclass
import json
import os
import subprocess
from typing import Any
from urllib.parse import quote
from urllib.request import Request, HTTPRedirectHandler, build_opener

from app.core.egress_policy import validate_public_http_target, EgressDenied


from app.core.governed_http import governed_request
@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    display_name: str
    capabilities: tuple[str, ...]
    auth_required: bool
    enabled: bool = True
    governance_class: str = "public_read"

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "display_name": self.display_name,
            "capabilities": list(self.capabilities),
            "auth_required": self.auth_required,
            "enabled": self.enabled,
            "governance_class": self.governance_class,
        }


@dataclass(frozen=True)
class SourceEvidence:
    source_id: str
    locator: str
    title: str | None
    content: str
    metadata: dict[str, Any]
    confidence: float = 0.7

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "locator": self.locator,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
            "confidence": self.confidence,
        }


SOURCES = (
    SourceSpec("web", "Web", ("read",), False),
    SourceSpec("web_search", "Web Search", ("search",), False),
    SourceSpec("twitter", "Twitter / X", ("read", "search", "thread"), True, governance_class="authenticated_read"),
    SourceSpec("reddit", "Reddit", ("read", "search"), False, governance_class="public_read_with_fallback"),
    SourceSpec("youtube", "YouTube", ("read", "search", "transcript"), False),
    SourceSpec("github", "GitHub", ("read", "search"), True, governance_class="authenticated_read"),
    SourceSpec("bilibili", "Bilibili", ("read", "search", "transcript"), False),
    SourceSpec("xiaohongshu", "XiaoHongShu", ("read", "search"), True, governance_class="authenticated_read"),
    SourceSpec("douyin", "Douyin", ("read", "search"), False),
    SourceSpec("wechat", "WeChat Articles", ("read", "search"), False),
    SourceSpec("linkedin", "LinkedIn", ("read", "search"), True, governance_class="authenticated_read"),
    SourceSpec("bosszhipin", "Boss Zhipin", ("read", "search"), True, governance_class="authenticated_read"),
    SourceSpec("rss", "RSS / Atom", ("read", "search"), False),
)


class ExternalIntelligence:
    VERSION = "1.0"
    MAX_BYTES = 2_000_000
    MAX_CONTENT = 60_000

    def catalog(self) -> list[dict[str, Any]]:
        return [item.as_dict() for item in SOURCES]

    @staticmethod
    def _command_exists(command: str) -> bool:
        from shutil import which
        return which(command) is not None

    @staticmethod
    def _public_url(url: str) -> bool:
        try:
            validate_public_http_target(url)
            return True
        except EgressDenied:
            return False

    def _fetch_url(self, url: str) -> SourceEvidence:
        if not self._public_url(url):
            raise ValueError("external_url_not_allowed")
        class _NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise ValueError("external_redirect_blocked")
        opener = build_opener(_NoRedirect)
        request = Request(url, headers={"User-Agent": "Kemet-External-Intelligence/1.0"})
        with opener.open(request, timeout=15) as response:
            content_type = response.headers.get("content-type", "")
            raw = response.read(self.MAX_BYTES)
        content = raw.decode("utf-8", errors="replace")[: self.MAX_CONTENT]
        return SourceEvidence("web", url, None, content, {"content_type": content_type}, 0.65)

    def _run_json(self, command: list[str], source_id: str, query: str) -> SourceEvidence:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"{source_id}_adapter_failed")
        output = completed.stdout[: self.MAX_CONTENT]
        try:
            parsed = json.loads(output)
            output = json.dumps(parsed, ensure_ascii=False, indent=2)[: self.MAX_CONTENT]
        except json.JSONDecodeError:
            pass
        return SourceEvidence(source_id, query, None, output, {"adapter": command[0]}, 0.7)

    def read(self, source_id: str, *, url: str | None = None, query: str | None = None) -> SourceEvidence:
        if source_id == "web":
            if not url:
                raise ValueError("url_required")
            return self._fetch_url(url)
        if source_id == "web_search":
            if not query:
                raise ValueError("query_required")
            url = "https://html.duckduckgo.com/html/?q=" + quote(query)
            evidence = self._fetch_url(url)
            return SourceEvidence("web_search", url, "Web search", evidence.content, evidence.metadata, 0.55)
        if source_id == "reddit":
            if not query:
                raise ValueError("query_required")
            url = "https://www.reddit.com/search.json?q=" + quote(query) + "&limit=10"
            evidence = self._fetch_url(url)
            return SourceEvidence("reddit", url, "Reddit search", evidence.content, evidence.metadata, 0.6)
        if source_id == "youtube":
            if not query:
                raise ValueError("query_required")
            if not self._command_exists("yt-dlp"):
                raise RuntimeError("youtube_adapter_unavailable")
            return self._run_json(["yt-dlp", "--dump-json", f"ytsearch5:{query}"], "youtube", query)
        if source_id == "twitter":
            if not query:
                raise ValueError("query_required")
            if not self._command_exists("xreach"):
                raise RuntimeError("twitter_adapter_unavailable")
            return self._run_json(["xreach", "search", query, "-n", "10", "--json"], "twitter", query)
        if source_id == "github":
            if not query:
                raise ValueError("query_required")
            if not self._command_exists("gh"):
                raise RuntimeError("github_adapter_unavailable")
            return self._run_json(
                ["gh", "search", "repos", query, "--limit", "10", "--json", "nameWithOwner,description,url,stargazerCount"],
                "github", query,
            )
        raise ValueError("source_not_implemented")


external_intelligence = ExternalIntelligence()
