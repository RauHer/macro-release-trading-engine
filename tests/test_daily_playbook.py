from datetime import date

from macro_engine.daily_playbook import build_daily_playbook


def test_daily_playbook_from_example_calendar():
    playbook = build_daily_playbook(
        "data/manual_forecasts/example_g10_calendar.csv",
        date(2026, 6, 11),
        "NQ",
        top=10,
    )

    assert playbook.symbol == "NQ"
    assert playbook.events
    assert all(event.relevance_score > 0 for event in playbook.events)
    assert "US2Y" in playbook.watchlist


def test_daily_playbook_filters_country():
    playbook = build_daily_playbook(
        "data/manual_forecasts/example_g10_calendar.csv",
        date(2026, 6, 11),
        "NQ",
        country="US",
    )

    assert playbook.events
    assert all(event.calendar_event.country_code == "US" for event in playbook.events)
