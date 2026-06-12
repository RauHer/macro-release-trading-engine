from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from .catalog import find_event
from .models import MacroRelease
from .sources import CalendarEvent
from .storage import load_manual_calendar_csv
from .symbol_profiles import SymbolProfile, get_symbol_profile


IMPACT_WEIGHT = {"high": 100, "medium": 60, "low": 25}


@dataclass
class PlaybookEvent:
    calendar_event: CalendarEvent
    relevance_score: int
    relevance_reason: str
    preliminary_direction: str
    confirmation: list[str]
    invalidation: list[str]
    trader_note: str


@dataclass
class PlaybookCluster:
    cluster_name: str
    scheduled_at: datetime | None
    events: list[PlaybookEvent]
    net_read: str
    trade_posture: str
    invalidation_logic: str
    confidence: str


@dataclass
class DailyPlaybook:
    target_date: date
    symbol: str
    display_name: str
    source_calendar: str
    events: list[PlaybookEvent]
    clusters: list[PlaybookCluster]
    summary: str
    watchlist: list[str] = field(default_factory=list)


def _event_channels(event_code: str, country_code: str) -> tuple[str, ...]:
    try:
        template = find_event(country_code, event_code)
        return tuple(c.value for c in template.channels)
    except Exception:
        return ("unknown",)


def _symbol_channel_relevance(profile: SymbolProfile, country_code: str, event_code: str, channels: tuple[str, ...]) -> tuple[int, str]:
    score = 0
    reasons: list[str] = []
    symbol_region = profile.region.upper()
    cc = country_code.upper()

    if cc in symbol_region or cc == "US" and profile.currency.upper().startswith("USD"):
        score += 25
        reasons.append("country/currency exposure matches the symbol")
    elif cc == "US" and profile.asset_class in {"equity_index", "single_stock", "fx_index", "fx"}:
        score += 20
        reasons.append("US macro has broad cross-asset transmission")

    dominant = {x.lower() for x in profile.dominant_channels}
    joined_channels = " ".join(channels).lower()
    if any(x in joined_channels for x in ["inflation", "central_bank", "liquidity"]):
        if profile.rate_sensitivity in {"high", "medium/high"} or profile.asset_class in {"equity_index", "single_stock", "fx", "fx_index"}:
            score += 30
            reasons.append("release can reprice rates/Fed path/liquidity")
    if "growth" in joined_channels or "labor" in joined_channels or "consumer" in joined_channels:
        if profile.macro_beta in {"high", "medium/high"} or profile.asset_class in {"equity_index", "single_stock"}:
            score += 20
            reasons.append("release can shift growth and risk-appetite expectations")
    if "housing" in joined_channels or "credit" in joined_channels:
        if profile.symbol in {"RTY", "ES", "NQ"} or profile.asset_class in {"equity_index", "single_stock"}:
            score += 10
            reasons.append("release touches rate-sensitive credit/housing channels")
    if "trade" in joined_channels or profile.asset_class in {"fx", "fx_index"}:
        if profile.asset_class in {"fx", "fx_index"}:
            score += 15
            reasons.append("release can affect FX/rate differentials")

    if not reasons:
        reasons.append("generic macro relevance; requires price confirmation")

    return score, "; ".join(reasons)


def _preliminary_direction(profile: SymbolProfile, event_code: str, country_code: str) -> str:
    channels = _event_channels(event_code, country_code)
    joined = " ".join(channels)
    if profile.asset_class in {"equity_index", "single_stock"}:
        if "inflation" in joined or "central_bank" in joined:
            return f"Two-sided before release: hotter/more hawkish is usually bearish {profile.symbol}; cooler/more dovish is usually bullish {profile.symbol}, unless growth-scare conditions dominate."
        if "labor" in joined:
            return f"Two-sided before release: hot wages/tight labor can be bearish {profile.symbol} through yields, while labor weakness can be bullish through rate relief or bearish through recession fear."
        if "growth" in joined or "consumer" in joined:
            return f"Conditional: stronger growth can support {profile.symbol} if rates stay contained, but can hurt if the regime punishes stronger data with higher yields."
    if profile.asset_class in {"fx", "fx_index"}:
        return f"Two-sided before release: stronger or more hawkish data should support the local currency/rate differential; weaker or more dovish data should pressure it, unless risk sentiment dominates."
    return "Two-sided before release; wait for actual value, deviation, and market confirmation."


def _confirmation(profile: SymbolProfile) -> list[str]:
    items = [f"{profile.symbol} breaks and holds away from the pre-release level"]
    items.extend(profile.confirmation_instruments)
    items.append("volatility/breadth confirms rather than contradicts the move")
    return list(dict.fromkeys(items))


def _invalidation(profile: SymbolProfile) -> list[str]:
    if profile.asset_class in {"equity_index", "single_stock"}:
        return [
            "2Y yield and 10Y yield do not confirm the rates interpretation",
            "DXY fails to confirm the macro impulse",
            f"{profile.symbol} reverses through the pre-release level after the initial move",
            "VIX, breadth, or sector leadership contradicts the intended trade",
        ]
    if profile.asset_class in {"fx", "fx_index"}:
        return [
            "rate differentials do not confirm",
            "DXY or the relevant FX cross reverses the release move",
            "risk sentiment overwhelms the macro/rates interpretation",
        ]
    return ["price action and related proxies contradict the macro interpretation"]


def _trader_note(profile: SymbolProfile, event: CalendarEvent) -> str:
    if event.forecast is not None:
        data_note = "Forecast is available, so the post-release assessment can use actual-vs-consensus deviation."
    elif event.previous is not None:
        data_note = "No forecast is available; treat the post-release assessment as previous-relative, not a true consensus surprise."
    else:
        data_note = "Forecast and previous are missing; this event needs qualitative interpretation and market confirmation."
    return f"{data_note} For {profile.symbol}, do not trade the calendar row by itself; wait for the actual release, deviation, and confirmation from the listed markets."


def _event_sort_key(item: PlaybookEvent) -> tuple[int, datetime]:
    when = item.calendar_event.scheduled_at or datetime.max
    return (-item.relevance_score, when)


def build_playbook_event(profile: SymbolProfile, event: CalendarEvent) -> PlaybookEvent:
    impact_score = IMPACT_WEIGHT.get(event.impact.lower(), 40)
    channels = _event_channels(event.event_code, event.country_code)
    channel_score, reason = _symbol_channel_relevance(profile, event.country_code, event.event_code, channels)
    relevance = impact_score + channel_score
    return PlaybookEvent(
        calendar_event=event,
        relevance_score=relevance,
        relevance_reason=reason,
        preliminary_direction=_preliminary_direction(profile, event.event_code, event.country_code),
        confirmation=_confirmation(profile),
        invalidation=_invalidation(profile),
        trader_note=_trader_note(profile, event),
    )


def _group_clusters(events: list[PlaybookEvent], window_minutes: int) -> list[PlaybookCluster]:
    dated = [e for e in events if e.calendar_event.scheduled_at is not None]
    clusters: list[list[PlaybookEvent]] = []
    for event in sorted(dated, key=lambda e: e.calendar_event.scheduled_at):
        placed = False
        for cluster in clusters:
            anchor = cluster[0].calendar_event.scheduled_at
            current = event.calendar_event.scheduled_at
            if anchor and current and abs(current - anchor) <= timedelta(minutes=window_minutes):
                cluster.append(event)
                placed = True
                break
        if not placed:
            clusters.append([event])

    output: list[PlaybookCluster] = []
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        country = cluster[0].calendar_event.country_code
        families = sorted({cluster_event.calendar_event.event_code for cluster_event in cluster})
        name = f"{country} release cluster: {', '.join(families)}"
        high_count = sum(1 for x in cluster if x.calendar_event.impact == "high")
        if high_count >= 2:
            confidence = "high importance, but direction depends on whether the releases align after actuals print"
        elif high_count == 1:
            confidence = "moderate importance; one high-impact release can dominate the cluster"
        else:
            confidence = "lower importance unless market reaction confirms"
        output.append(
            PlaybookCluster(
                cluster_name=name,
                scheduled_at=cluster[0].calendar_event.scheduled_at,
                events=cluster,
                net_read="Pre-release cluster. Direction is unknown until actuals print. After release, assess whether the individual events are aligned, mixed, or contradictory.",
                trade_posture="Do not front-run the cluster. Use the cluster as a volatility window, then trade only after actual deviations and confirmation markets agree.",
                invalidation_logic="Stand aside if the cluster produces mixed data and the queried symbol, rates, USD, volatility, or breadth do not resolve the conflict.",
                confidence=confidence,
            )
        )
    return output


def build_daily_playbook(calendar_path: str | Path, target_date: date, symbol: str, impact: str | None = None, country: str | None = None, top: int = 20, cluster_window_minutes: int = 5) -> DailyPlaybook:
    profile = get_symbol_profile(symbol)
    raw_events = load_manual_calendar_csv(calendar_path)
    events = [e for e in raw_events if e.scheduled_at is None or e.scheduled_at.date() == target_date]
    if impact:
        events = [e for e in events if e.impact.lower() == impact.lower()]
    if country:
        events = [e for e in events if e.country_code.upper() == country.upper()]

    playbook_events = [build_playbook_event(profile, e) for e in events]
    playbook_events = sorted(playbook_events, key=_event_sort_key)[:top]
    clusters = _group_clusters(playbook_events, cluster_window_minutes)
    watchlist = list(dict.fromkeys(profile.confirmation_instruments))

    if playbook_events:
        summary = f"Daily playbook built for {profile.symbol}. Highest-ranked events should be treated as volatility/catalyst windows, not automatic trades. Trade direction comes after actual deviation and confirmation."
    else:
        summary = f"No matching events found for {target_date}."

    return DailyPlaybook(
        target_date=target_date,
        symbol=profile.symbol,
        display_name=profile.display_name,
        source_calendar=str(calendar_path),
        events=playbook_events,
        clusters=clusters,
        summary=summary,
        watchlist=watchlist,
    )


def render_daily_playbook(playbook: DailyPlaybook) -> str:
    lines = [
        f"Daily Macro Playbook — {playbook.target_date.isoformat()}",
        f"Symbol: {playbook.symbol} — {playbook.display_name}",
        f"Calendar: {playbook.source_calendar}",
        "",
        "Playbook Summary:",
        playbook.summary,
        "",
        "Core Trade Rule:",
        "- This is a pre-release playbook. It identifies what to care about before the data prints.",
        "- Do not treat the calendar event as a trade signal by itself.",
        "- Final trade direction requires actual-vs-forecast or actual-vs-previous assessment plus confirmation from price, rates, USD/FX, volatility, and related proxies.",
        "",
        "Confirmation Watchlist:",
    ]
    for item in playbook.watchlist:
        lines.append(f"- {item}")

    if playbook.clusters:
        lines.extend(["", "Release Clusters To Watch:"])
        for cluster in playbook.clusters:
            when = cluster.scheduled_at.isoformat() if cluster.scheduled_at else "unscheduled"
            lines.extend(
                [
                    f"\n{when} — {cluster.cluster_name}",
                    f"- Confidence: {cluster.confidence}",
                    f"- Net read before release: {cluster.net_read}",
                    f"- Trade posture: {cluster.trade_posture}",
                    f"- Invalidation/no-trade logic: {cluster.invalidation_logic}",
                    "- Events:",
                ]
            )
            for event in cluster.events:
                ce = event.calendar_event
                lines.append(f"  - {ce.country_code}/{ce.event_code} {ce.name} [{ce.impact}] forecast={ce.forecast} previous={ce.previous}")

    lines.extend(["", "Ranked Event Plan:"])
    for idx, item in enumerate(playbook.events, start=1):
        event = item.calendar_event
        when = event.scheduled_at.isoformat() if event.scheduled_at else "unscheduled"
        lines.extend(
            [
                f"\n{idx}. {when} — {event.country_code}/{event.event_code}: {event.name}",
                f"- Impact: {event.impact}",
                f"- Relevance score for {playbook.symbol}: {item.relevance_score}",
                f"- Why it matters: {item.relevance_reason}",
                f"- Pre-release directional framework: {item.preliminary_direction}",
                f"- Forecast: {event.forecast}",
                f"- Previous: {event.previous}",
                f"- Trader note: {item.trader_note}",
                "- Confirmation checklist:",
            ]
        )
        for confirm in item.confirmation:
            lines.append(f"  - {confirm}")
        lines.append("- Invalidation / no-trade conditions:")
        for invalid in item.invalidation:
            lines.append(f"  - {invalid}")
    return "\n".join(lines)
