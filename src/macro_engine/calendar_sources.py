from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .source_adapters import SOURCE_ADAPTERS, build_all_source_adapters, build_source_adapter
from .sources import CalendarEvent, CalendarSource


def summarize_error(exc: Exception, limit: int = 500) -> str:
    """Return a concise single-line source error.

    Some public sites return very large HTML/JavaScript bodies when blocked or
    when pandas cannot find parseable tables. Diagnostics should identify the
    failure without dumping an entire webpage into the terminal.
    """
    text = str(exc).replace("\r", " ").replace("\n", " ").strip()
    lowered = text.lower()
    if "<html" in lowered or "<script" in lowered or "document.getelementbyid" in lowered:
        text = "HTML/JavaScript page returned instead of parseable calendar data; likely dynamic page, login wall, or anti-bot response."
    if len(text) > limit:
        text = text[:limit].rstrip() + " ... [truncated]"
    return text


@dataclass(frozen=True)
class PublicCalendarPreset:
    key: str
    name: str
    url: str
    adapter: str
    notes: str = ""


PUBLIC_CALENDAR_PRESETS: dict[str, PublicCalendarPreset] = {
    "forexfactory": PublicCalendarPreset(
        key="forexfactory",
        name="Forex Factory Calendar",
        url="https://www.forexfactory.com/calendar",
        adapter="ForexFactoryCalendarAdapter",
        notes="Primary first target; attempts export-style endpoints before HTML fallback.",
    ),
    "myfxbook": PublicCalendarPreset(
        key="myfxbook",
        name="Myfxbook Economic Calendar",
        url="https://www.myfxbook.com/forex-economic-calendar",
        adapter="MyfxbookCalendarAdapter",
        notes="Potentially table-oriented; may require login/export handling.",
    ),
    "fxstreet": PublicCalendarPreset(
        key="fxstreet",
        name="FXStreet Economic Calendar",
        url="https://www.fxstreet.com/economic-calendar",
        adapter="FXStreetCalendarAdapter",
        notes="May require custom dynamic-page handling if generic HTML tables are absent.",
    ),
    "investing": PublicCalendarPreset(
        key="investing",
        name="Investing.com Economic Calendar",
        url="https://www.investing.com/economic-calendar/",
        adapter="InvestingCalendarAdapter",
        notes="Broad coverage but commonly dynamic/anti-bot; fallback source.",
    ),
    "tradingeconomics": PublicCalendarPreset(
        key="tradingeconomics",
        name="Trading Economics Calendar",
        url="https://tradingeconomics.com/calendar",
        adapter="TradingEconomicsCalendarAdapter",
        notes="Excellent model; API-backed adapter likely best long term.",
    ),
    "financialjuice": PublicCalendarPreset(
        key="financialjuice",
        name="FinancialJuice News Stream",
        url="https://www.financialjuice.com/home",
        adapter="FinancialJuiceNewsAdapter",
        notes="Better as future headline/squawk adapter than primary calendar.",
    ),
}


class PresetCalendarSource(CalendarSource):
    """CalendarSource wrapper for a named public calendar preset."""

    def __init__(self, preset_key: str):
        key = preset_key.lower()
        if key not in PUBLIC_CALENDAR_PRESETS:
            valid = ", ".join(sorted(PUBLIC_CALENDAR_PRESETS))
            raise KeyError(f"Unknown calendar preset '{preset_key}'. Valid presets: {valid}")
        self.preset = PUBLIC_CALENDAR_PRESETS[key]
        self.source_name = self.preset.key
        self._source = build_source_adapter(key)

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        return self._source.fetch_calendar(target_date)


@dataclass
class SourceAttempt:
    source: str
    ok: bool
    events: int
    error: str | None = None


@dataclass
class MultiSourceCalendarResult:
    events: list[CalendarEvent]
    attempts: list[SourceAttempt]


class MultiSourceCalendar(CalendarSource):
    """Try several sources and deduplicate normalized calendar events.

    Each source is allowed to fail without stopping the workflow. Successful
    results are merged using a conservative key: country, event code,
    scheduled timestamp/date, and event name.
    """

    source_name = "multi_source"

    def __init__(self, sources: Iterable[CalendarSource]):
        self.sources = list(sources)

    def fetch_calendar_result(self, target_date: date) -> MultiSourceCalendarResult:
        all_events: list[CalendarEvent] = []
        attempts: list[SourceAttempt] = []
        for source in self.sources:
            name = getattr(source, "source_name", source.__class__.__name__)
            try:
                events = source.fetch_calendar(target_date)
                attempts.append(SourceAttempt(source=name, ok=True, events=len(events)))
                all_events.extend(events)
            except Exception as exc:  # intentionally source-isolated
                attempts.append(SourceAttempt(source=name, ok=False, events=0, error=summarize_error(exc)))
        return MultiSourceCalendarResult(events=dedupe_calendar_events(all_events), attempts=attempts)

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        return self.fetch_calendar_result(target_date).events


def build_preset_sources(keys: Iterable[str] | None = None) -> list[CalendarSource]:
    selected = list(keys) if keys else list(SOURCE_ADAPTERS.keys())
    return build_all_source_adapters(selected)


def dedupe_calendar_events(events: Iterable[CalendarEvent]) -> list[CalendarEvent]:
    seen: dict[tuple[str, str, str, str], CalendarEvent] = {}
    for event in events:
        when = event.scheduled_at.isoformat(timespec="minutes") if event.scheduled_at else "unscheduled"
        key = (event.country_code, event.event_code, when, event.name.strip().lower())
        if key not in seen:
            seen[key] = event
            continue
        existing = seen[key]
        if existing.forecast is None and event.forecast is not None:
            existing.forecast = event.forecast
        if existing.previous is None and event.previous is not None:
            existing.previous = event.previous
        if existing.actual is None and event.actual is not None:
            existing.actual = event.actual
        existing.source = "+".join(sorted(set(filter(None, [existing.source, event.source]))))
    return sorted(
        seen.values(),
        key=lambda e: (e.scheduled_at or __import__("datetime").datetime.max, e.country_code, e.event_code, e.name),
    )
