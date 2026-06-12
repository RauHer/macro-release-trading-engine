from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .sources import CalendarEvent, CalendarSource, GenericHTMLCalendarSource


@dataclass(frozen=True)
class PublicCalendarPreset:
    key: str
    name: str
    url: str
    adapter: str = "generic_html"
    notes: str = ""


PUBLIC_CALENDAR_PRESETS: dict[str, PublicCalendarPreset] = {
    "forexfactory": PublicCalendarPreset(
        key="forexfactory",
        name="Forex Factory Calendar",
        url="https://www.forexfactory.com/calendar",
        notes="Best candidate for a source-specific adapter because Forex Factory exposes export-style calendar formats, but generic HTML parsing may not be enough.",
    ),
    "myfxbook": PublicCalendarPreset(
        key="myfxbook",
        name="Myfxbook Economic Calendar",
        url="https://www.myfxbook.com/forex-economic-calendar",
        notes="Likely table-oriented; may require login or custom handling for export endpoints.",
    ),
    "fxstreet": PublicCalendarPreset(
        key="fxstreet",
        name="FXStreet Economic Calendar",
        url="https://www.fxstreet.com/economic-calendar",
        notes="Useful event model with consensus/actual/deviation concepts; likely needs a custom adapter if rendered dynamically.",
    ),
    "investing": PublicCalendarPreset(
        key="investing",
        name="Investing.com Economic Calendar",
        url="https://www.investing.com/economic-calendar/",
        notes="Broad coverage but often dynamic/anti-bot; use as a fallback source, not the backbone.",
    ),
    "tradingeconomics": PublicCalendarPreset(
        key="tradingeconomics",
        name="Trading Economics Calendar",
        url="https://tradingeconomics.com/calendar",
        notes="Excellent data model; best long-term path is probably API-backed rather than scraped HTML.",
    ),
    "financialjuice": PublicCalendarPreset(
        key="financialjuice",
        name="FinancialJuice News Stream",
        url="https://www.financialjuice.com/home",
        notes="Better suited to headline/squawk ingestion than primary economic calendar ingestion.",
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
        self._source = GenericHTMLCalendarSource(self.preset.url, source_name=self.preset.key)

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        events = self._source.fetch_calendar(target_date)
        for event in events:
            if not event.source:
                event.source = self.preset.key
            if not event.source_url:
                event.source_url = self.preset.url
            if self.preset.notes and self.preset.notes not in event.notes:
                event.notes = f"{event.notes} {self.preset.notes}".strip()
        return events


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

    This is the key redundancy layer. Each source is allowed to fail without
    stopping the workflow. Successful results are merged using a conservative
    key: country, event code, scheduled timestamp/date, and event name.
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
                attempts.append(SourceAttempt(source=name, ok=False, events=0, error=str(exc)))
        return MultiSourceCalendarResult(events=dedupe_calendar_events(all_events), attempts=attempts)

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        return self.fetch_calendar_result(target_date).events


def build_preset_sources(keys: Iterable[str] | None = None) -> list[PresetCalendarSource]:
    selected = list(keys) if keys else list(PUBLIC_CALENDAR_PRESETS.keys())
    return [PresetCalendarSource(key) for key in selected]


def dedupe_calendar_events(events: Iterable[CalendarEvent]) -> list[CalendarEvent]:
    seen: dict[tuple[str, str, str, str], CalendarEvent] = {}
    for event in events:
        when = event.scheduled_at.isoformat(timespec="minutes") if event.scheduled_at else "unscheduled"
        key = (event.country_code, event.event_code, when, event.name.strip().lower())
        if key not in seen:
            seen[key] = event
            continue
        existing = seen[key]
        # Prefer rows with forecasts/actuals and keep source provenance.
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
