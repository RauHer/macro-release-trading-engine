from macro_engine.models import MacroRelease
from macro_engine.symbol_impact import assess_symbol_impact_for_cluster, assess_symbol_impact_for_release


def test_hot_cpi_bearish_nq_symbol_impact():
    report = assess_symbol_impact_for_release(
        "NQ",
        MacroRelease(country_code="US", event_code="CPI", actual=3.4, forecast=3.2, previous=3.1),
    )

    assert report.symbol == "NQ"
    assert report.direction == "Bearish NQ"
    assert "2Y yield" in " ".join(report.invalidation_conditions)
    assert report.release_assessment is not None


def test_mixed_labor_cluster_conditional_nq():
    report = assess_symbol_impact_for_cluster(
        "NQ",
        [
            MacroRelease(country_code="US", event_code="EMPLOYMENT_CHANGE", actual=250000, forecast=180000, previous=190000),
            MacroRelease(country_code="US", event_code="UNEMPLOYMENT", actual=4.1, forecast=3.9, previous=3.9),
            MacroRelease(country_code="US", event_code="WAGES", actual=0.4, forecast=0.3, previous=0.2),
        ],
    )

    assert report.cluster_assessment is not None
    assert report.cluster_assessment.alignment == "mixed_labor"
    assert "Conditional" in report.direction or report.direction.startswith("Wait")
    assert "market confirmation" in report.confidence.lower()
