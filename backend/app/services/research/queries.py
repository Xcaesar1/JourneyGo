"""Generate a bounded set of time-sensitive travel research queries."""

from __future__ import annotations

from datetime import date

from ...domain.research_models import ClaimType, ResearchQuery, stable_research_id
from ...domain.trip_models import TripRequestV2

_QUERY_TEMPLATES: dict[str, dict[ClaimType, str]] = {
    "zh": {
        "opening_hours": "{city} {window} 营业时间 官方",
        "closure": "{city} {window} 临时闭馆 维护 公告 官方",
        "reservation": "{city} {window} 预约 门票 实名 规则 官方",
        "events": "{city} {window} 活动 展览 节庆 官方",
        "travel_tips": "{city} {window} 旅行提示 交通 安全 官方",
    },
    "en": {
        "opening_hours": "{city} {window} opening hours official",
        "closure": "{city} {window} temporary closure maintenance official notice",
        "reservation": "{city} {window} reservation ticket entry rules official",
        "events": "{city} {window} events exhibitions festivals official",
        "travel_tips": "{city} {window} travel advisory transport safety official",
    },
    "ja": {
        "opening_hours": "{city} {window} 営業時間 公式",
        "closure": "{city} {window} 臨時休館 メンテナンス 公式 お知らせ",
        "reservation": "{city} {window} 予約 チケット 入場規則 公式",
        "events": "{city} {window} イベント 展覧会 祭り 公式",
        "travel_tips": "{city} {window} 旅行情報 交通 安全 公式",
    },
}

_PRIORITIES: dict[ClaimType, tuple[int, bool]] = {
    "closure": (100, True),
    "reservation": (90, True),
    "opening_hours": (80, True),
    "events": (70, True),
    "travel_tips": (50, False),
}


def _date_window(start_date: date, end_date: date) -> str:
    return f"{start_date.isoformat()} {end_date.isoformat()}"


def prepare_research_queries(request: TripRequestV2) -> list[ResearchQuery]:
    """Return exactly five prioritized, repeatable queries per destination."""
    language = request.language.lower().split("-", 1)[0]
    templates = _QUERY_TEMPLATES.get(language, _QUERY_TEMPLATES["en"])
    window = _date_window(request.start_date, request.end_date)
    queries: list[ResearchQuery] = []

    for destination in request.destinations:
        for claim_type, template in templates.items():
            query_text = template.format(city=destination.city, window=window)
            priority, critical = _PRIORITIES[claim_type]
            queries.append(
                ResearchQuery(
                    id=stable_research_id(
                        destination.city,
                        claim_type,
                        request.start_date.isoformat(),
                        request.end_date.isoformat(),
                        language,
                    ),
                    city=destination.city,
                    claim_type=claim_type,
                    query=query_text,
                    priority=priority,
                    critical=critical,
                )
            )

    return sorted(queries, key=lambda item: (-item.priority, item.city, str(item.id)))

