from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

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
    source: str | None = None


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
