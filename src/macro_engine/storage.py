from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from .sources import CalendarEvent

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MANUAL_FORECASTS_DIR = DATA_DIR / "manual_forecasts"


def ensure_data_dirs() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, MANUAL_FORECASTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _event_to_row(event: CalendarEvent) -> dict[str, str | float | None]:
    return {
        "country_code": event.country_code,
        "event_code": event.event_code,
        "name": event.name,
        "scheduled_at": event.scheduled_at.isoformat() if event.scheduled_at else "",
        "impact": event.impact,
        "forecast": event.forecast,
        "previous": event.previous,
        "actual": event.actual,
        "unit": event.unit,
        "source": event.source,
        "source_url": event.source_url,
        "notes": event.notes,
    }


def save_calendar_events(events: Iterable[CalendarEvent], target_date: date, label: str = "calendar") -> Path:
    ensure_data_dirs()
    path = PROCESSED_DIR / f"{label}_{target_date.isoformat()}.csv"
    rows = [_event_to_row(e) for e in events]
    fieldnames = [
        "country_code", "event_code", "name", "scheduled_at", "impact", "forecast",
        "previous", "actual", "unit", "source", "source_url", "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def save_raw_text(text: str, target_date: date, source_name: str, suffix: str = "html") -> Path:
    ensure_data_dirs()
    safe_source = source_name.lower().replace(" ", "_").replace("/", "_")
    path = RAW_DIR / f"{safe_source}_{target_date.isoformat()}.{suffix}"
    path.write_text(text, encoding="utf-8")
    return path


def load_manual_calendar_csv(path: str | Path) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    p = Path(path)
    with p.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            scheduled_raw = (row.get("scheduled_at") or "").strip()
            scheduled_at = datetime.fromisoformat(scheduled_raw) if scheduled_raw else None
            events.append(
                CalendarEvent(
                    country_code=(row.get("country_code") or "").upper(),
                    event_code=(row.get("event_code") or "").upper(),
                    name=row.get("name") or row.get("event") or "Unknown Event",
                    scheduled_at=scheduled_at,
                    impact=(row.get("impact") or "medium").lower(),
                    forecast=_parse_optional_float(row.get("forecast")),
                    previous=_parse_optional_float(row.get("previous")),
                    actual=_parse_optional_float(row.get("actual")),
                    unit=row.get("unit") or None,
                    source=row.get("source") or "manual_csv",
                    source_url=row.get("source_url") or None,
                    notes=row.get("notes") or "",
                )
            )
    return events


def _parse_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).replace("%", "").replace(",", "").strip()
    if not cleaned or cleaned.upper() in {"NA", "N/A", "NONE", "-"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None
