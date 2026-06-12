from macro_engine.calendar_impact import build_calendar_cluster_impact, build_calendar_symbol_impact


CALENDAR = "data/manual_forecasts/example_g10_calendar.csv"


def test_calendar_symbol_impact_loads_forecast_previous():
    report = build_calendar_symbol_impact(
        calendar_path=CALENDAR,
        symbol="NQ",
        country="US",
        event="CPI",
        actual=3.4,
    )

    assert report.symbol == "NQ"
    assert report.release_assessment is not None
    assert report.release_assessment.forecast == 3.2
    assert report.release_assessment.previous == 3.1
    assert report.direction == "Bearish NQ"


def test_calendar_cluster_impact_handles_duplicate_event_codes():
    report = build_calendar_cluster_impact(
        calendar_path=CALENDAR,
        symbol="NQ",
        country="US",
        events=["CPI", "CORE_CPI"],
        actuals=[3.4, 3.5],
    )

    assert report.cluster_assessment is not None
    assert report.cluster_assessment.cluster_type == "inflation"
    assert report.direction == "Bearish NQ"
