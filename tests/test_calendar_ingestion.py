from datetime import date
from pathlib import Path

from macro_engine.sources import ManualCalendarCSVSource


def test_manual_calendar_csv_loads_example():
    path = Path("data/manual_forecasts/example_g10_calendar.csv")
    source = ManualCalendarCSVSource(path)
    events = source.fetch_calendar(date(2026, 6, 11))
    assert len(events) >= 10
    assert any(e.country_code == "US" and e.event_code == "CPI" for e in events)
    assert all(e.impact == "high" for e in events)
