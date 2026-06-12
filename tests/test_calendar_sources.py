from datetime import datetime

from macro_engine.calendar_sources import PUBLIC_CALENDAR_PRESETS, dedupe_calendar_events
from macro_engine.source_adapters import SOURCE_ADAPTERS, build_source_adapter
from macro_engine.sources import CalendarEvent


def test_all_presets_have_adapters():
    for key in PUBLIC_CALENDAR_PRESETS:
        assert key in SOURCE_ADAPTERS
        adapter = build_source_adapter(key)
        assert adapter.source_name == key


def test_dedupe_merges_forecast_values():
    a = CalendarEvent(
        country_code="US",
        event_code="CPI",
        name="Consumer Price Index",
        scheduled_at=datetime(2026, 6, 11, 8, 30),
        impact="high",
        forecast=None,
        source="a",
    )
    b = CalendarEvent(
        country_code="US",
        event_code="CPI",
        name="Consumer Price Index",
        scheduled_at=datetime(2026, 6, 11, 8, 30),
        impact="high",
        forecast=3.2,
        source="b",
    )
    out = dedupe_calendar_events([a, b])
    assert len(out) == 1
    assert out[0].forecast == 3.2
    assert out[0].source == "a+b"
