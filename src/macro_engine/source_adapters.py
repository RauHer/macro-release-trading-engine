from __future__ import annotations

from datetime import date, datetime, timedelta
from urllib.parse import urlencode

import pandas as pd
import requests
from dateutil import parser as dtparser

from .sources import CalendarEvent, CalendarSource, GenericHTMLCalendarSource, _infer_country_code, _infer_event_code, _parse_optional_float


class ForexFactoryCalendarAdapter(CalendarSource):
    """Forex Factory adapter.

    Forex Factory is the best first target because it has historically exposed
    calendar export formats. The adapter tries export-style endpoints first and
    falls back to the generic HTML parser.
    """

    source_name = "forexfactory"
    base_url = "https://www.forexfactory.com/calendar"

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        # Export endpoints change over time, so keep the attempts isolated.
        errors: list[str] = []
        for url in self._candidate_urls(target_date):
            try:
                events = self._fetch_csv_like(url, target_date)
                if events:
                    return events
            except Exception as exc:
                errors.append(f"{url}: {exc}")
        try:
            return GenericHTMLCalendarSource(self.base_url, source_name=self.source_name).fetch_calendar(target_date)
        except Exception as exc:
            errors.append(f"html fallback: {exc}")
            raise RuntimeError("ForexFactory adapter failed: " + " | ".join(errors))

    def _candidate_urls(self, target_date: date) -> list[str]:
        week_start = target_date - timedelta(days=target_date.weekday())
        # These are intentionally candidates, not promises. Probe diagnostics
        # will tell us which, if any, works in the current public site state.
        return [
            f"https://nfs.faireconomy.media/ff_calendar_thisweek.csv",
            f"https://nfs.faireconomy.media/ff_calendar_thisweek.xml",
            f"https://nfs.faireconomy.media/ff_calendar_{week_start:%Y%m%d}.csv",
        ]

    def _fetch_csv_like(self, url: str, target_date: date) -> list[CalendarEvent]:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 macro-release-trading-engine/0.1"}, timeout=20)
        response.raise_for_status()
        text = response.text.strip()
        if not text or "<html" in text.lower():
            return []
        if url.endswith(".xml"):
            return self._parse_xml(text, target_date, url)
        from io import StringIO
        df = pd.read_csv(StringIO(text))
        return _calendar_events_from_dataframe(df, target_date, self.source_name, url)

    def _parse_xml(self, text: str, target_date: date, url: str) -> list[CalendarEvent]:
        try:
            frames = pd.read_xml(text)
        except Exception:
            return []
        if isinstance(frames, pd.DataFrame):
            return _calendar_events_from_dataframe(frames, target_date, self.source_name, url)
        return []


class MyfxbookCalendarAdapter(CalendarSource):
    source_name = "myfxbook"
    url = "https://www.myfxbook.com/forex-economic-calendar"

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        return GenericHTMLCalendarSource(self.url, source_name=self.source_name).fetch_calendar(target_date)


class FXStreetCalendarAdapter(CalendarSource):
    source_name = "fxstreet"
    url = "https://www.fxstreet.com/economic-calendar"

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        return GenericHTMLCalendarSource(self.url, source_name=self.source_name).fetch_calendar(target_date)


class InvestingCalendarAdapter(CalendarSource):
    source_name = "investing"
    url = "https://www.investing.com/economic-calendar/"

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        return GenericHTMLCalendarSource(self.url, source_name=self.source_name).fetch_calendar(target_date)


class TradingEconomicsCalendarAdapter(CalendarSource):
    source_name = "tradingeconomics"
    url = "https://tradingeconomics.com/calendar"

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        return GenericHTMLCalendarSource(self.url, source_name=self.source_name).fetch_calendar(target_date)


class FinancialJuiceNewsAdapter(CalendarSource):
    """FinancialJuice placeholder.

    FinancialJuice is treated as a future news/squawk adapter rather than a
    primary economic calendar. For now, the adapter probes the public page via
    the generic table parser only.
    """

    source_name = "financialjuice"
    url = "https://www.financialjuice.com/home"

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        return GenericHTMLCalendarSource(self.url, source_name=self.source_name).fetch_calendar(target_date)


SOURCE_ADAPTERS: dict[str, type[CalendarSource]] = {
    "forexfactory": ForexFactoryCalendarAdapter,
    "myfxbook": MyfxbookCalendarAdapter,
    "fxstreet": FXStreetCalendarAdapter,
    "investing": InvestingCalendarAdapter,
    "tradingeconomics": TradingEconomicsCalendarAdapter,
    "financialjuice": FinancialJuiceNewsAdapter,
}


def build_source_adapter(key: str) -> CalendarSource:
    k = key.lower().strip()
    if k not in SOURCE_ADAPTERS:
        valid = ", ".join(sorted(SOURCE_ADAPTERS))
        raise KeyError(f"Unknown source adapter '{key}'. Valid: {valid}")
    return SOURCE_ADAPTERS[k]()


def build_all_source_adapters(keys: list[str] | None = None) -> list[CalendarSource]:
    selected = keys or list(SOURCE_ADAPTERS.keys())
    return [build_source_adapter(key) for key in selected]


def _calendar_events_from_dataframe(df: pd.DataFrame, target_date: date, source_name: str, source_url: str) -> list[CalendarEvent]:
    if df.empty:
        return []
    work = df.copy()
    work.columns = [str(c).strip().lower().replace(" ", "_").replace("/", "_") for c in work.columns]
    events: list[CalendarEvent] = []
    for _, row in work.iterrows():
        name = _first_present(row, ["event", "title", "name", "indicator"])
        if not name:
            continue
        country_raw = _first_present(row, ["currency", "country", "region"])
        country_code = _infer_country_code(pd.Series({"country": country_raw}), {"country": "country"}) if country_raw else ""
        if not country_code:
            continue
        scheduled_at = _parse_event_datetime(row, target_date)
        if scheduled_at and scheduled_at.date() != target_date:
            continue
        impact = str(_first_present(row, ["impact", "importance", "priority"]) or "medium").lower()
        events.append(
            CalendarEvent(
                country_code=country_code,
                event_code=_infer_event_code(str(name)),
                name=str(name),
                scheduled_at=scheduled_at,
                impact="high" if "high" in impact else "low" if "low" in impact else "medium",
                forecast=_parse_optional_float(_first_present(row, ["forecast", "consensus", "estimate"])),
                previous=_parse_optional_float(_first_present(row, ["previous", "prior"])),
                actual=_parse_optional_float(_first_present(row, ["actual", "latest"])),
                source=source_name,
                source_url=source_url,
                notes="Parsed by source-specific adapter helper; verify before trading.",
            )
        )
    return events


def _first_present(row: pd.Series, names: list[str]) -> object | None:
    for name in names:
        if name in row and pd.notna(row[name]):
            value = row[name]
            if str(value).strip():
                return value
    return None


def _parse_event_datetime(row: pd.Series, target_date: date) -> datetime | None:
    raw_date = _first_present(row, ["date", "day"]) or target_date.isoformat()
    raw_time = _first_present(row, ["time"])
    raw = " ".join(str(x) for x in [raw_date, raw_time] if x is not None and str(x).lower() != "nan")
    try:
        return dtparser.parse(raw, default=datetime(target_date.year, target_date.month, target_date.day))
    except Exception:
        return None
