from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .calendar_sources import PresetCalendarSource
from .models import MacroRelease
from .sources import CalendarEvent
from .storage import load_manual_calendar_csv, save_calendar_events
from .symbol_impact import SymbolImpactReport, assess_symbol_impact_for_cluster, assess_symbol_impact_for_release


@dataclass(frozen=True)
class CalendarMatch:
    event: CalendarEvent
    match_reason: str


@dataclass(frozen=True)
class AutoImpactResult:
    report: SymbolImpactReport
    refreshed_calendar_path: Path
    matched_events: list[CalendarEvent]


def _norm(value: str | None) -> str:
    return (value or "").strip().upper()


def _matches_from_events(events: list[CalendarEvent], country: str, event_code: str) -> list[CalendarMatch]:
    country_key = _norm(country)
    event_key = _norm(event_code)
    exact: list[CalendarMatch] = []
    fallback: list[CalendarMatch] = []
    for event in events:
        if _norm(event.country_code) != country_key:
            continue
        if _norm(event.event_code) == event_key:
            exact.append(CalendarMatch(event=event, match_reason="exact country/event_code match"))
        elif event_key and event_key in _norm(event.name):
            fallback.append(CalendarMatch(event=event, match_reason="country/name contains requested event text"))
    return exact or fallback


def _find_calendar_matches(calendar_path: str | Path, country: str, event_code: str) -> list[CalendarMatch]:
    return _matches_from_events(load_manual_calendar_csv(calendar_path), country, event_code)


def _select_from_matches(matches: list[CalendarMatch], country: str, event_code: str, source_label: str, occurrence: int = 1) -> CalendarEvent:
    if not matches:
        raise ValueError(f"No calendar row found for {country}/{event_code} in {source_label}")
    if occurrence < 1:
        raise ValueError("Occurrence must be 1 or greater.")
    if occurrence > len(matches):
        available = ", ".join(f"{m.event.name} at {m.event.scheduled_at}" for m in matches)
        raise ValueError(f"Requested occurrence {occurrence}, but only {len(matches)} match(es) found: {available}")
    return sorted(matches, key=lambda m: m.event.scheduled_at or m.event.name)[occurrence - 1].event


def _select_calendar_event(calendar_path: str | Path, country: str, event_code: str, occurrence: int = 1) -> CalendarEvent:
    matches = _find_calendar_matches(calendar_path, country, event_code)
    return _select_from_matches(matches, country, event_code, str(calendar_path), occurrence)


def _calendar_event_to_release(event: CalendarEvent, actual: float | None, require_actual: bool = False) -> MacroRelease:
    actual_value = actual if actual is not None else event.actual
    if require_actual and actual_value is None:
        raise ValueError(
            f"Actual value is not available yet for {event.country_code}/{event.event_code} — {event.name}. "
            "Refresh again after the release source posts the actual, or use the manual --actual fallback."
        )
    return MacroRelease(
        country_code=event.country_code,
        event_code=event.event_code,
        actual=actual_value,
        forecast=event.forecast,
        previous=event.previous,
        unit=event.unit,
        released_at=event.scheduled_at,
        source=event.source,
        quality_warnings=[f"Calendar metadata loaded from {event.source}; verify source values before trading."],
    )


def build_calendar_symbol_impact(
    *,
    calendar_path: str | Path,
    symbol: str,
    country: str,
    event: str,
    actual: float | None,
    occurrence: int = 1,
) -> SymbolImpactReport:
    calendar_event = _select_calendar_event(calendar_path, country, event, occurrence=occurrence)
    release = _calendar_event_to_release(calendar_event, actual)
    return assess_symbol_impact_for_release(symbol, release)


def build_calendar_cluster_impact(
    *,
    calendar_path: str | Path,
    symbol: str,
    country: str,
    events: list[str],
    actuals: list[float | None],
) -> SymbolImpactReport:
    if len(events) != len(actuals):
        raise ValueError(f"Expected {len(events)} actual values, got {len(actuals)}")
    occurrence_counter: dict[str, int] = {}
    releases: list[MacroRelease] = []
    for idx, event_code in enumerate(events):
        key = _norm(event_code)
        occurrence_counter[key] = occurrence_counter.get(key, 0) + 1
        calendar_event = _select_calendar_event(calendar_path, country, event_code, occurrence=occurrence_counter[key])
        releases.append(_calendar_event_to_release(calendar_event, actuals[idx]))
    return assess_symbol_impact_for_cluster(symbol, releases)


def _refresh_calendar(preset: str, target_date: date, country: str | None = None) -> tuple[list[CalendarEvent], Path]:
    source = PresetCalendarSource(preset)
    events = source.fetch_calendar(target_date)
    if country:
        events = [event for event in events if _norm(event.country_code) == _norm(country)]
    path = save_calendar_events(events, target_date, label=f"{preset}_auto_refresh")
    return events, path


def build_auto_calendar_symbol_impact(
    *,
    preset: str,
    target_date: date,
    symbol: str,
    country: str,
    event: str,
    occurrence: int = 1,
) -> AutoImpactResult:
    refreshed_events, path = _refresh_calendar(preset, target_date, country=country)
    matched_event = _select_from_matches(
        _matches_from_events(refreshed_events, country, event),
        country,
        event,
        source_label=f"{preset} auto-refresh",
        occurrence=occurrence,
    )
    release = _calendar_event_to_release(matched_event, actual=None, require_actual=True)
    report = assess_symbol_impact_for_release(symbol, release)
    return AutoImpactResult(report=report, refreshed_calendar_path=path, matched_events=[matched_event])


def build_auto_calendar_cluster_impact(
    *,
    preset: str,
    target_date: date,
    symbol: str,
    country: str,
    events: list[str],
) -> AutoImpactResult:
    refreshed_events, path = _refresh_calendar(preset, target_date, country=country)
    occurrence_counter: dict[str, int] = {}
    matched_events: list[CalendarEvent] = []
    releases: list[MacroRelease] = []
    for event_code in events:
        key = _norm(event_code)
        occurrence_counter[key] = occurrence_counter.get(key, 0) + 1
        matched_event = _select_from_matches(
            _matches_from_events(refreshed_events, country, event_code),
            country,
            event_code,
            source_label=f"{preset} auto-refresh",
            occurrence=occurrence_counter[key],
        )
        matched_events.append(matched_event)
        releases.append(_calendar_event_to_release(matched_event, actual=None, require_actual=True))
    report = assess_symbol_impact_for_cluster(symbol, releases)
    return AutoImpactResult(report=report, refreshed_calendar_path=path, matched_events=matched_events)
