from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dateutil import parser as dtparser

from .catalog import CATALOG, COUNTRIES
from .models import MacroRelease


@dataclass
class CalendarEvent:
    country_code: str
    event_code: str
    name: str
    scheduled_at: datetime | None
    impact: str
    forecast: float | None = None
    previous: float | None = None
    actual: float | None = None
    unit: str | None = None
    source: str | None = None
    source_url: str | None = None
    notes: str = ""


class CalendarSource(ABC):
    """Interface for public economic calendar adapters."""

    source_name: str

    @abstractmethod
    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        raise NotImplementedError


class OfficialDataSource(ABC):
    """Interface for official actual-data adapters."""

    source_name: str

    @abstractmethod
    def fetch_release(self, country_code: str, event_code: str, target_date: date) -> MacroRelease | None:
        raise NotImplementedError


class ManualReleaseSource:
    """Simple manual source used until event-specific scrapers are hardened.

    This intentionally exists because free consensus data is fragile. A manual
    override path prevents the whole trading workflow from depending on one
    website's HTML structure.
    """

    source_name = "manual"

    @staticmethod
    def build_release(
        country_code: str,
        event_code: str,
        actual: float | None,
        forecast: float | None,
        previous: float | None = None,
        revised_previous: float | None = None,
        unit: str | None = None,
    ) -> MacroRelease:
        return MacroRelease(
            country_code=country_code.upper(),
            event_code=event_code.upper(),
            actual=actual,
            forecast=forecast,
            previous=previous,
            revised_previous=revised_previous,
            unit=unit,
            source="manual",
        )


class ManualCalendarCSVSource(CalendarSource):
    """Load normalized calendar rows from a local CSV file.

    Required columns: country_code, event_code, name. Optional columns:
    scheduled_at, impact, forecast, previous, actual, unit, source_url, notes.
    """

    source_name = "manual_csv"

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        from .storage import load_manual_calendar_csv

        events = load_manual_calendar_csv(self.csv_path)
        return [e for e in events if e.scheduled_at is None or e.scheduled_at.date() == target_date]


class GenericHTMLCalendarSource(CalendarSource):
    """Best-effort adapter for public pages exposing ordinary HTML tables.

    This is intentionally generic and conservative. It should not be treated as
    a guaranteed parser for JavaScript-heavy or anti-bot protected websites.
    The source is useful for public pages whose tables include some combination
    of date/time, country/currency, event, impact, forecast, previous, actual.
    """

    source_name = "generic_html"

    def __init__(self, url: str, source_name: str | None = None, timeout: int = 20):
        self.url = url
        self.source_name = source_name or self.source_name
        self.timeout = timeout

    def fetch_calendar(self, target_date: date) -> list[CalendarEvent]:
        response = requests.get(
            self.url,
            headers={"User-Agent": "Mozilla/5.0 macro-release-trading-engine/0.1"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        tables = pd.read_html(response.text)
        events: list[CalendarEvent] = []
        for table in tables:
            events.extend(self._parse_table(table, target_date))
        return events

    def _parse_table(self, df: pd.DataFrame, target_date: date) -> list[CalendarEvent]:
        if df.empty:
            return []
        work = df.copy()
        work.columns = [_normalize_col(c) for c in work.columns]
        colmap = _infer_calendar_columns(list(work.columns))
        if "event" not in colmap:
            return []
        rows: list[CalendarEvent] = []
        for _, row in work.iterrows():
            event_name = str(row.get(colmap["event"], "")).strip()
            if not event_name or event_name.lower() in {"nan", "none"}:
                continue
            country_code = _infer_country_code(row, colmap)
            if country_code not in COUNTRIES:
                continue
            event_code = _infer_event_code(event_name)
            scheduled_at = _infer_datetime(row, colmap, target_date)
            if scheduled_at is not None and scheduled_at.date() != target_date:
                continue
            rows.append(
                CalendarEvent(
                    country_code=country_code,
                    event_code=event_code,
                    name=event_name,
                    scheduled_at=scheduled_at,
                    impact=_infer_impact(row, colmap),
                    forecast=_parse_optional_float(row.get(colmap.get("forecast"))) if "forecast" in colmap else None,
                    previous=_parse_optional_float(row.get(colmap.get("previous"))) if "previous" in colmap else None,
                    actual=_parse_optional_float(row.get(colmap.get("actual"))) if "actual" in colmap else None,
                    source=self.source_name,
                    source_url=self.url,
                    notes="Parsed by GenericHTMLCalendarSource; verify before trading.",
                )
            )
        return rows


def _normalize_col(col: Any) -> str:
    return str(col).strip().lower().replace(" ", "_").replace("/", "_")


def _infer_calendar_columns(columns: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for col in columns:
        c = col.lower()
        if c in {"event", "indicator", "release", "name"} or "event" in c:
            out.setdefault("event", col)
        elif c in {"country", "currency", "region"} or "country" in c or "currency" in c:
            out.setdefault("country", col)
        elif c in {"date", "day"} or c.endswith("date"):
            out.setdefault("date", col)
        elif c in {"time"} or c.endswith("time"):
            out.setdefault("time", col)
        elif "impact" in c or "importance" in c or "priority" in c:
            out.setdefault("impact", col)
        elif "forecast" in c or "consensus" in c or "estimate" in c:
            out.setdefault("forecast", col)
        elif "previous" in c or "prior" in c:
            out.setdefault("previous", col)
        elif "actual" in c or "latest" in c:
            out.setdefault("actual", col)
    return out


def _infer_country_code(row: pd.Series, colmap: dict[str, str]) -> str:
    raw = str(row.get(colmap.get("country"), "")).strip().upper()
    aliases = {
        "USD": "US", "UNITED STATES": "US", "US": "US", "USA": "US",
        "EUR": "EA", "EURO AREA": "EA", "EUROZONE": "EA", "EMU": "EA",
        "GBP": "UK", "UNITED KINGDOM": "UK", "UK": "UK", "BRITAIN": "UK",
        "JPY": "JP", "JAPAN": "JP", "JP": "JP",
        "CAD": "CA", "CANADA": "CA", "CA": "CA",
        "AUD": "AU", "AUSTRALIA": "AU", "AU": "AU",
        "NZD": "NZ", "NEW ZEALAND": "NZ", "NZ": "NZ",
        "CHF": "CH", "SWITZERLAND": "CH", "CH": "CH",
        "SEK": "SE", "SWEDEN": "SE", "SE": "SE",
        "NOK": "NO", "NORWAY": "NO", "NO": "NO",
    }
    return aliases.get(raw, raw)


def _infer_event_code(name: str) -> str:
    n = name.lower()
    for event in CATALOG:
        if event.event_code.lower() in n or event.name.lower() in n:
            return event.event_code
    patterns = [
        ("CORE_CPI", ["core cpi", "core consumer price"]),
        ("CPI", ["cpi", "consumer price", "inflation rate"]),
        ("PPI", ["ppi", "producer price"]),
        ("GDP", ["gdp", "gross domestic"]),
        ("UNEMPLOYMENT", ["unemployment", "jobless rate"]),
        ("EMPLOYMENT_CHANGE", ["payroll", "employment change", "jobs", "employment"]),
        ("WAGES", ["wage", "earnings", "labor cost", "labour cost"]),
        ("RETAIL_SALES", ["retail sales"]),
        ("PMI_MFG", ["manufacturing pmi", "factory pmi"]),
        ("PMI_SERVICES", ["services pmi", "service pmi"]),
        ("CENTRAL_BANK_RATE", ["rate decision", "interest rate", "policy rate"]),
        ("CENTRAL_BANK_STATEMENT", ["statement", "press conference"]),
        ("CENTRAL_BANK_MINUTES", ["minutes"]),
        ("INDUSTRIAL_PRODUCTION", ["industrial production"]),
        ("TRADE_BALANCE", ["trade balance"]),
        ("HOUSING", ["housing", "building permits", "starts"]),
        ("CONFIDENCE", ["confidence", "sentiment"]),
    ]
    for code, needles in patterns:
        if any(x in n for x in needles):
            return code
    return "UNKNOWN"


def _infer_datetime(row: pd.Series, colmap: dict[str, str], target_date: date) -> datetime | None:
    date_part = str(row.get(colmap.get("date"), target_date.isoformat())).strip()
    time_part = str(row.get(colmap.get("time"), "")).strip()
    raw = " ".join(x for x in [date_part, time_part] if x and x.lower() != "nan")
    if not raw:
        return None
    try:
        return dtparser.parse(raw, default=datetime(target_date.year, target_date.month, target_date.day))
    except Exception:
        return None


def _infer_impact(row: pd.Series, colmap: dict[str, str]) -> str:
    raw = str(row.get(colmap.get("impact"), "medium")).strip().lower()
    if any(x in raw for x in ["high", "3", "red", "major"]):
        return "high"
    if any(x in raw for x in ["low", "1", "minor"]):
        return "low"
    return "medium"


def _parse_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    cleaned = str(value).replace("%", "").replace(",", "").strip()
    if not cleaned or cleaned.lower() in {"nan", "na", "n/a", "none", "-"}:
        return None
    multiplier = 1.0
    if cleaned.endswith("K"):
        multiplier = 1_000.0
        cleaned = cleaned[:-1]
    elif cleaned.endswith("M"):
        multiplier = 1_000_000.0
        cleaned = cleaned[:-1]
    elif cleaned.endswith("B"):
        multiplier = 1_000_000_000.0
        cleaned = cleaned[:-1]
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None
