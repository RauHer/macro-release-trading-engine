from __future__ import annotations

import math

from .catalog import find_event
from .models import AssetClass, MacroRelease, SurpriseResult


HAWKISH_TYPES = {"hawkish_risk_off", "growth_positive_hawkish"}
GROWTH_POSITIVE_TYPES = {"growth_positive", "currency_positive"}
GROWTH_NEGATIVE_DOVISH_TYPES = {"growth_negative_dovish"}


def _safe_float(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def _clip(value: float, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _directional_multiplier(higher_is: str) -> int:
    if higher_is in HAWKISH_TYPES:
        return -1
    if higher_is in GROWTH_NEGATIVE_DOVISH_TYPES:
        return -1
    if higher_is in GROWTH_POSITIVE_TYPES:
        return 1
    return 0


def _macro_impulse(higher_is: str, raw_surprise: float | None) -> str:
    if raw_surprise is None:
        return "unknown"
    if abs(raw_surprise) < 1e-12:
        return "in_line"
    direction = "higher" if raw_surprise > 0 else "lower"
    if higher_is == "hawkish_risk_off":
        return f"{direction}_than_expected_policy_hawkish" if raw_surprise > 0 else "lower_than_expected_policy_dovish"
    if higher_is == "growth_positive_hawkish":
        return f"{direction}_than_expected_growth_and_policy_pressure"
    if higher_is == "growth_negative_dovish":
        return "labor_slack_or_growth_weakness" if raw_surprise > 0 else "labor_tightness_or_growth_resilience"
    if higher_is == "growth_positive":
        return "growth_upside" if raw_surprise > 0 else "growth_downside"
    if higher_is == "currency_positive":
        return "currency_supportive" if raw_surprise > 0 else "currency_negative"
    return "contextual_manual_interpretation_required"


def _asset_bias(event_sensitivity: dict[AssetClass, int], directional_score: float) -> dict[str, str]:
    bias: dict[str, str] = {}
    for asset, sensitivity in event_sensitivity.items():
        impulse = sensitivity * directional_score
        if impulse > 35:
            label = "strong_bullish"
        elif impulse > 10:
            label = "bullish"
        elif impulse < -35:
            label = "strong_bearish"
        elif impulse < -10:
            label = "bearish"
        else:
            label = "neutral_or_contextual"
        bias[asset.value] = label
    return bias


def score_release(release: MacroRelease) -> SurpriseResult:
    event = find_event(release.country_code, release.event_code)
    warnings: list[str] = list(release.quality_warnings)

    actual = _safe_float(release.actual)
    forecast = _safe_float(release.forecast)
    previous = _safe_float(release.previous)
    revised_previous = _safe_float(release.revised_previous)

    raw_surprise: float | None = None
    revision_surprise: float | None = None

    if actual is None:
        warnings.append("Missing actual value; cannot produce valid post-release score.")
    if forecast is None:
        warnings.append("Missing forecast/consensus value; score will be low confidence.")

    if actual is not None and forecast is not None:
        raw_surprise = actual - forecast

    if revised_previous is not None and previous is not None:
        revision_surprise = revised_previous - previous

    if raw_surprise is None:
        standardized = 0.0
    else:
        # Initial deterministic scaling. Later phases should replace this with
        # event-specific historical surprise distributions.
        denominator = abs(forecast) if forecast not in (None, 0) else max(abs(previous or 0), 1.0)
        standardized = _clip((raw_surprise / denominator) * 100.0, -100.0, 100.0)

    multiplier = _directional_multiplier(event.higher_is)
    if multiplier == 0:
        directional_score = 0.0
        warnings.append("Contextual event type; manual interpretation required before trading.")
    else:
        directional_score = _clip(standardized * multiplier)

    # Revision shock matters, but should not dominate actual-vs-consensus surprise.
    if revision_surprise is not None and previous not in (None, 0):
        revision_scaled = _clip((revision_surprise / abs(previous)) * 30.0, -15.0, 15.0)
        directional_score = _clip(directional_score + revision_scaled * multiplier)

    confidence = 1.0
    if actual is None:
        confidence -= 0.55
    if forecast is None:
        confidence -= 0.30
    if event.higher_is == "contextual":
        confidence -= 0.25
    if warnings:
        confidence -= min(0.25, 0.05 * len(warnings))
    confidence = max(0.0, round(confidence, 2))

    return SurpriseResult(
        country_code=event.country_code,
        event_code=event.event_code,
        event_name=event.name,
        actual=actual,
        forecast=forecast,
        previous=previous,
        revised_previous=revised_previous,
        raw_surprise=raw_surprise,
        revision_surprise=revision_surprise,
        standardized_surprise=round(standardized, 2),
        directional_score=round(directional_score, 2),
        macro_impulse=_macro_impulse(event.higher_is, raw_surprise),
        asset_bias=_asset_bias(event.asset_sensitivity, directional_score),
        confidence=confidence,
        warnings=warnings,
        details={
            "higher_is": event.higher_is,
            "impact": event.impact.value,
            "channels": [c.value for c in event.channels],
            "note": "Historical surprise distributions and market reaction confirmation are roadmap items.",
        },
    )


def classify_trade_bias(result: SurpriseResult) -> str:
    score = result.directional_score
    if result.confidence < 0.45:
        return "NO_TRADE_LOW_CONFIDENCE"
    if score >= 40:
        return "STRONG_RISK_ON_OR_LOCAL_ASSET_BULLISH"
    if score >= 15:
        return "MODERATE_RISK_ON_OR_LOCAL_ASSET_BULLISH"
    if score <= -40:
        return "STRONG_RISK_OFF_OR_LOCAL_ASSET_BEARISH"
    if score <= -15:
        return "MODERATE_RISK_OFF_OR_LOCAL_ASSET_BEARISH"
    return "NEUTRAL_OR_WAIT_FOR_MARKET_CONFIRMATION"
