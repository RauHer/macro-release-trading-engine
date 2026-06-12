from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .catalog import find_event
from .models import MacroRelease


class AssessmentType(str, Enum):
    FORECAST_RELATIVE = "forecast_relative_surprise"
    PREVIOUS_RELATIVE = "previous_relative_change"
    REVISION_RELATIVE = "revision_relative_change"
    THRESHOLD_RELATIVE = "threshold_relative_signal"
    CONTEXTUAL = "contextual_manual_interpretation"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class ReleaseAssessment:
    country_code: str
    event_code: str
    event_name: str
    actual: float | None
    forecast: float | None
    previous: float | None
    revised_previous: float | None
    unit: str | None
    assessment_type: AssessmentType
    absolute_deviation: float | None = None
    relative_deviation_pct: float | None = None
    previous_change: float | None = None
    previous_change_pct: float | None = None
    revision_change: float | None = None
    revision_change_pct: float | None = None
    mathematical_comparison: str = "Unavailable"
    trader_interpretation: str = "Unavailable"
    first_macro_read: str = "Unavailable"
    threshold_context: str | None = None
    confidence_label: str = "low"
    warnings: list[str] = field(default_factory=list)


def _fmt_num(value: float | None) -> str:
    if value is None:
        return "unavailable"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:g}"


def _pct_change(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return (numerator / abs(denominator)) * 100.0


def _comparison(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    if value > 0:
        return "Greater than"
    if value < 0:
        return "Lesser than"
    return "In line with"


def _event_interpretation(event_code: str, higher_is: str, comparison: str, basis: str) -> tuple[str, str]:
    if comparison == "Unavailable":
        return "Unavailable", "Insufficient data to produce a precise macro read."

    greater = comparison.startswith("Greater")
    lesser = comparison.startswith("Lesser")

    if event_code in {"CPI", "CORE_CPI", "PPI", "INFLATION_EXPECTATIONS", "WAGES"}:
        if greater:
            return "Hotter than forecast" if basis == "forecast" else "Hotter than previous", "Hawkish inflation/Fed-path impulse; potentially negative for duration-sensitive equities if yields confirm."
        if lesser:
            return "Cooler than forecast" if basis == "forecast" else "Cooler than previous", "Dovish inflation/Fed-path impulse; potentially supportive for duration-sensitive equities if growth fear does not dominate."
        return "In line", "No meaningful inflation surprise from the headline comparison."

    if event_code in {"UNEMPLOYMENT", "JOBLESS_CLAIMS"}:
        if greater:
            return "Weaker labor market signal", "Growth-negative and potentially dovish-rates impulse; risk assets may still sell off if recession fear dominates."
        if lesser:
            return "Stronger labor market signal", "Labor-tightness / growth-resilience impulse; can be hawkish for rates if the market focuses on Fed path."
        return "In line", "No meaningful labor-market deviation from the comparison basis."

    if event_code in {"EMPLOYMENT_CHANGE", "RETAIL_SALES", "GDP", "PMI_MFG", "PMI_SERVICES", "INDUSTRIAL_PRODUCTION", "CONFIDENCE", "HOUSING", "BUILDING_PERMITS", "TOURISM"}:
        if greater:
            return "Stronger than forecast" if basis == "forecast" else "Stronger than previous", "Growth-positive impulse; equity impact depends on whether the regime rewards growth or punishes rates pressure."
        if lesser:
            return "Weaker than forecast" if basis == "forecast" else "Weaker than previous", "Growth-negative impulse; may support rate-cut expectations but can become risk-off if growth-scare conditions dominate."
        return "In line", "No meaningful growth deviation from the comparison basis."

    if event_code == "CENTRAL_BANK_RATE":
        if greater:
            return "More hawkish than expected" if basis == "forecast" else "More restrictive than previous", "Hawkish policy impulse; front-end yields and local currency should confirm."
        if lesser:
            return "More dovish than expected" if basis == "forecast" else "Less restrictive than previous", "Dovish policy impulse; equity response depends on whether the cut/easing is interpreted as support or panic."
        return "In line", "Rate decision itself was in line; statement and press conference may dominate."

    if event_code == "ENERGY_INVENTORIES":
        if greater:
            return "Larger inventory build", "Potentially bearish commodity impulse unless seasonal, weather, or demand context says otherwise."
        if lesser:
            return "Smaller inventory build / larger draw", "Potentially supportive commodity impulse if demand/supply context confirms."
        return "In line", "No meaningful inventory-flow deviation from the comparison basis."

    if event_code == "BOND_AUCTION":
        if greater:
            return "Higher clearing yield than comparison basis", "Potential weak-demand / higher term-premium signal, but auction quality requires tail, bid-to-cover, and bidder-detail confirmation."
        if lesser:
            return "Lower clearing yield than comparison basis", "Potential stronger-demand / lower term-premium signal, but auction quality requires tail, bid-to-cover, and bidder-detail confirmation."
        return "In line", "Auction headline is in line; bid metrics may dominate."

    if higher_is == "hawkish_risk_off":
        return ("Hotter / more hawkish" if greater else "Cooler / more dovish" if lesser else "In line"), "Policy-path impulse should be confirmed by rates and FX."
    if higher_is in {"growth_positive", "growth_positive_hawkish", "currency_positive"}:
        return ("Stronger" if greater else "Weaker" if lesser else "In line"), "Growth/currency impulse requires regime and market confirmation."
    if higher_is == "growth_negative_dovish":
        return ("Weaker" if greater else "Stronger" if lesser else "In line"), "Growth-negative events require careful risk-vs-rates interpretation."
    return "Contextual", "Manual interpretation required; market confirmation should dominate."


def _threshold_context(event_code: str, actual: float | None) -> str | None:
    if actual is None:
        return None
    if event_code in {"PMI_MFG", "PMI_SERVICES"}:
        if actual > 50:
            return "Above 50, indicating expansionary survey conditions."
        if actual < 50:
            return "Below 50, indicating contractionary survey conditions."
        return "At 50, the expansion/contraction threshold."
    return None


def assess_release(release: MacroRelease) -> ReleaseAssessment:
    event = find_event(release.country_code, release.event_code)
    warnings: list[str] = list(release.quality_warnings)

    actual = release.actual
    forecast = release.forecast
    previous = release.previous
    revised_previous = release.revised_previous

    absolute_deviation: float | None = None
    relative_deviation_pct: float | None = None
    previous_change: float | None = None
    previous_change_pct: float | None = None
    revision_change: float | None = None
    revision_change_pct: float | None = None

    if actual is None:
        warnings.append("Missing actual value; cannot assess release precisely.")
        assessment_type = AssessmentType.INSUFFICIENT_DATA
        mathematical_comparison = "Unavailable"
        trader_interpretation = "Unavailable"
        first_macro_read = "Actual value is missing."
        confidence = "low"
    elif forecast is not None:
        absolute_deviation = actual - forecast
        relative_deviation_pct = _pct_change(absolute_deviation, forecast)
        assessment_type = AssessmentType.FORECAST_RELATIVE
        cmp = _comparison(absolute_deviation)
        mathematical_comparison = f"{cmp} forecast" if cmp != "Unavailable" else cmp
        trader_interpretation, first_macro_read = _event_interpretation(event.event_code, event.higher_is, cmp, "forecast")
        confidence = "high" if abs(absolute_deviation) > 0 else "moderate"
    elif previous is not None:
        previous_change = actual - previous
        previous_change_pct = _pct_change(previous_change, previous)
        assessment_type = AssessmentType.PREVIOUS_RELATIVE
        cmp = _comparison(previous_change)
        mathematical_comparison = f"{cmp} previous" if cmp != "Unavailable" else cmp
        trader_interpretation, first_macro_read = _event_interpretation(event.event_code, event.higher_is, cmp, "previous")
        warnings.append("No forecast/consensus value available; assessment is previous-relative, not a true consensus surprise.")
        confidence = "moderate/low"
    else:
        assessment_type = AssessmentType.INSUFFICIENT_DATA
        mathematical_comparison = "Unavailable"
        trader_interpretation = "Unavailable"
        first_macro_read = "Forecast and previous values are missing, so only qualitative interpretation is possible."
        warnings.append("Missing both forecast and previous value; no deviation can be calculated.")
        confidence = "low"

    if revised_previous is not None and previous is not None:
        revision_change = revised_previous - previous
        revision_change_pct = _pct_change(revision_change, previous)

    threshold = _threshold_context(event.event_code, actual)
    if threshold and assessment_type == AssessmentType.PREVIOUS_RELATIVE:
        assessment_type = AssessmentType.THRESHOLD_RELATIVE

    return ReleaseAssessment(
        country_code=event.country_code,
        event_code=event.event_code,
        event_name=event.name,
        actual=actual,
        forecast=forecast,
        previous=previous,
        revised_previous=revised_previous,
        unit=release.unit,
        assessment_type=assessment_type,
        absolute_deviation=absolute_deviation,
        relative_deviation_pct=relative_deviation_pct,
        previous_change=previous_change,
        previous_change_pct=previous_change_pct,
        revision_change=revision_change,
        revision_change_pct=revision_change_pct,
        mathematical_comparison=mathematical_comparison,
        trader_interpretation=trader_interpretation,
        first_macro_read=first_macro_read,
        threshold_context=threshold,
        confidence_label=confidence,
        warnings=warnings,
    )


def render_release_assessment(assessment: ReleaseAssessment) -> str:
    lines = [
        f"Event: {assessment.country_code}/{assessment.event_code} — {assessment.event_name}",
        "",
        "Actual Announcement Assessment:",
        f"- Actual: {_fmt_num(assessment.actual)}",
        f"- Forecast: {_fmt_num(assessment.forecast)}",
        f"- Previous: {_fmt_num(assessment.previous)}",
    ]
    if assessment.revised_previous is not None:
        lines.append(f"- Revised previous: {_fmt_num(assessment.revised_previous)}")
    if assessment.absolute_deviation is not None:
        lines.append(f"- Absolute deviation vs forecast: {assessment.absolute_deviation:+g}")
    if assessment.relative_deviation_pct is not None:
        lines.append(f"- Relative deviation vs forecast: {assessment.relative_deviation_pct:+.2f}%")
    if assessment.previous_change is not None:
        lines.append(f"- Absolute change vs previous: {assessment.previous_change:+g}")
    if assessment.previous_change_pct is not None:
        lines.append(f"- Relative change vs previous: {assessment.previous_change_pct:+.2f}%")
    if assessment.revision_change is not None:
        lines.append(f"- Revision change: {assessment.revision_change:+g}")
    if assessment.revision_change_pct is not None:
        lines.append(f"- Revision change percentage: {assessment.revision_change_pct:+.2f}%")
    lines.extend(
        [
            f"- Mathematical comparison: {assessment.mathematical_comparison}",
            f"- Trader interpretation: {assessment.trader_interpretation}",
        ]
    )
    if assessment.threshold_context:
        lines.append(f"- Threshold context: {assessment.threshold_context}")
    lines.extend(
        [
            f"- Assessment type: {assessment.assessment_type.value}",
            f"- Confidence: {assessment.confidence_label}",
            f"- First macro read: {assessment.first_macro_read}",
        ]
    )
    if assessment.warnings:
        lines.append("- Warnings:")
        for warning in assessment.warnings:
            lines.append(f"  - {warning}")
    return "\n".join(lines)
