"""Optional Ctrip Wendao source for supplementary attraction names."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

LOGGER = logging.getLogger(__name__)
TRIPAI_QUERY_URL = "https://wendao-skill-prod.ctrip.com/skill/query"

_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+•]|\d+[.)、])\s*(.+?)\s*$")
_MARKDOWN_LINK_RE = re.compile(r"\[([^]]+)]\([^)]+\)")
_TABLE_SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")
_REJECTED_PHRASES = (
    "以下",
    "推荐理由",
    "行程",
    "有需要",
    "希望",
    "祝你",
    "随时",
)


@dataclass(frozen=True)
class SupplementalAttractionResult:
    names: tuple[str, ...] = ()
    issue: str | None = None


class SupplementalAttractionSource(Protocol):
    def recommend(
        self,
        city: str,
        *,
        interests: tuple[str, ...] = (),
        limit: int = 6,
    ) -> SupplementalAttractionResult: ...


def _clean_candidate(value: str) -> str:
    candidate = _MARKDOWN_LINK_RE.sub(r"\1", value)
    candidate = re.sub(r"[*_`#]", "", candidate).strip()
    candidate = re.sub(r"^(?:景点(?:名称)?|名称)\s*[：:]\s*", "", candidate)
    return candidate.strip(" \t-|｜")


def _looks_like_attraction_name(value: str) -> bool:
    if not 2 <= len(value) <= 40:
        return False
    if any(marker in value for marker in "，。！？；;：:"):
        return False
    lowered = value.casefold()
    return not any(phrase.casefold() in lowered for phrase in _REJECTED_PHRASES)


def parse_tripai_attraction_names(payload: Any, *, limit: int = 6) -> list[str]:
    """Parse conservative attraction names from Wendao Markdown output."""
    if isinstance(payload, dict):
        content = payload.get("result")
        if not isinstance(content, str):
            content = payload.get("content")
    else:
        content = payload
    if not isinstance(content, str) or not content.strip():
        return []

    names: list[str] = []
    for raw_line in content.replace("```markdown", "").replace("```", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _LIST_ITEM_RE.match(line)
        candidate = match.group(1) if match else ""
        if not candidate and "|" in line:
            cells = [_clean_candidate(cell) for cell in line.strip("|").split("|")]
            cells = [cell for cell in cells if cell and not _TABLE_SEPARATOR_RE.match(cell)]
            if cells and cells[0] in {"序号", "编号", "名称", "景点"}:
                continue
            if cells and cells[0].isdigit():
                cells = cells[1:]
            candidate = cells[0] if cells else ""
        candidate = _clean_candidate(candidate)
        if not _looks_like_attraction_name(candidate) or candidate in names:
            continue
        names.append(candidate)
        if len(names) >= max(1, min(limit, 8)):
            break
    return names


class CtripWendaoSupplementalSource:
    """Fetch names only; AMap remains responsible for validating every POI."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = TRIPAI_QUERY_URL,
        client: httpx.Client | None = None,
        timeout: float = 30,
    ) -> None:
        if not api_key.strip():
            raise ValueError("TRIPAI_API_KEY is required when TripAI is enabled.")
        self._api_key = api_key.strip()
        self._base_url = base_url.strip() or TRIPAI_QUERY_URL
        self._client = client or httpx.Client(timeout=timeout)

    def recommend(
        self,
        city: str,
        *,
        interests: tuple[str, ...] = (),
        limit: int = 6,
    ) -> SupplementalAttractionResult:
        interest_text = "、".join(interests) if interests else "综合热门"
        bounded_limit = max(1, min(limit, 8))
        query = (
            f"请推荐{city}最值得游览、符合{interest_text}偏好的{bounded_limit}个景点。"
            "只返回Markdown无序列表，每项仅写高德地图可检索的正式景点名称，不要说明、图片或路线。"
        )
        try:
            response = self._client.post(
                self._base_url,
                json={"token": self._api_key, "query": query, "source": "github"},
            )
            response.raise_for_status()
            try:
                payload: Any = response.json()
            except ValueError:
                payload = response.text
        except httpx.HTTPStatusError as exc:
            issue = "tripai_rate_limited" if exc.response.status_code == 429 else "tripai_request_failed"
            LOGGER.warning(
                "TripAI supplemental request failed city=%s status=%s",
                city,
                exc.response.status_code,
            )
            return SupplementalAttractionResult(issue=issue)
        except httpx.HTTPError as exc:
            LOGGER.warning(
                "TripAI supplemental request failed city=%s error=%s",
                city,
                type(exc).__name__,
            )
            return SupplementalAttractionResult(issue="tripai_request_failed")

        names = parse_tripai_attraction_names(payload, limit=bounded_limit)
        if not names:
            return SupplementalAttractionResult(issue="tripai_invalid_response")
        return SupplementalAttractionResult(names=tuple(names))
