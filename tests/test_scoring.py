from macro_engine.models import MacroRelease
from macro_engine.scoring import classify_trade_bias, score_release


def test_hot_us_cpi_scores_risk_off():
    result = score_release(
        MacroRelease(country_code="US", event_code="CPI", actual=3.4, forecast=3.2, previous=3.1)
    )
    assert result.raw_surprise > 0
    assert result.directional_score < 0
    assert "bearish" in result.asset_bias["equity_index"]


def test_growth_upside_gdp_scores_risk_on():
    result = score_release(
        MacroRelease(country_code="US", event_code="GDP", actual=2.8, forecast=2.2, previous=2.0)
    )
    assert result.raw_surprise > 0
    assert result.directional_score > 0
    assert classify_trade_bias(result) != "NO_TRADE_LOW_CONFIDENCE"


def test_missing_forecast_lowers_confidence():
    result = score_release(
        MacroRelease(country_code="UK", event_code="CPI", actual=3.4, forecast=None, previous=3.1)
    )
    assert result.confidence < 1.0
    assert result.raw_surprise is None
