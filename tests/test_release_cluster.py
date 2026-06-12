from macro_engine.models import MacroRelease
from macro_engine.release_cluster import assess_release_cluster


def test_aligned_hot_inflation_cluster():
    cluster = assess_release_cluster(
        [
            MacroRelease(country_code="US", event_code="CPI", actual=3.4, forecast=3.2, previous=3.1),
            MacroRelease(country_code="US", event_code="CORE_CPI", actual=3.5, forecast=3.3, previous=3.2),
        ]
    )

    assert cluster.cluster_type == "inflation"
    assert cluster.alignment == "aligned_hawkish"
    assert "duration-sensitive equities" in cluster.equity_impulse


def test_mixed_labor_cluster():
    cluster = assess_release_cluster(
        [
            MacroRelease(country_code="US", event_code="EMPLOYMENT_CHANGE", actual=250000, forecast=180000, previous=190000),
            MacroRelease(country_code="US", event_code="UNEMPLOYMENT", actual=4.1, forecast=3.9, previous=3.9),
            MacroRelease(country_code="US", event_code="WAGES", actual=0.4, forecast=0.3, previous=0.2),
        ]
    )

    assert cluster.cluster_type == "labor"
    assert cluster.alignment == "mixed_labor"
    assert cluster.conflict_warnings
