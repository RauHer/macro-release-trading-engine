from __future__ import annotations

from datetime import datetime

from .catalog import COUNTRIES, find_event
from .models import MacroRelease, SurpriseResult
from .scoring import classify_trade_bias, score_release


def render_pre_release(country_code: str, event_code: str) -> str:
    event = find_event(country_code, event_code)
    country = COUNTRIES[event.country_code]
    lines = [
        f"# Pre-Release Playbook — {country.name} {event.name}",
        "",
        f"**Country:** {country.name} ({event.country_code})",
        f"**Currency:** {country.currency}",
        f"**Central Bank:** {country.central_bank}",
        f"**Impact:** {event.impact.value.upper()}",
        f"**Channels:** {', '.join(c.value for c in event.channels)}",
        f"**Higher-Is Interpretation:** {event.higher_is}",
        "",
        "## Primary Transmission Questions",
        "",
        "1. Does the release change growth expectations?",
        "2. Does the release change inflation expectations?",
        "3. Does the release change the central-bank path?",
        "4. Do rates and FX confirm the headline interpretation?",
        "5. Does the equity-index reaction hold after the first liquidity burst?",
        "",
        "## Expected Asset Sensitivity",
        "",
        "| Asset Class | Sensitivity |",
        "|---|---:|",
    ]
    for asset, value in event.asset_sensitivity.items():
        lines.append(f"| {asset.value} | {value:+d} |")

    lines += [
        "",
        "## Trading Workflow",
        "",
        "- Avoid initiating discretionary trades immediately before high-impact releases unless the setup is explicitly event-driven.",
        "- Score actual vs forecast first; then check revisions.",
        "- Validate with rates and FX before trusting the equity-index reaction.",
        "- If rates/FX and equities disagree, classify as conflict/no-trade until confirmation emerges.",
        "",
    ]
    return "\n".join(lines)


def render_post_release(result: SurpriseResult) -> str:
    country = COUNTRIES[result.country_code]
    trade_bias = classify_trade_bias(result)
    lines = [
        f"# Post-Release Report — {country.name} {result.event_name}",
        "",
        f"**Generated:** {datetime.utcnow().isoformat(timespec='seconds')}Z",
        f"**Country:** {country.name} ({result.country_code})",
        f"**Event:** {result.event_name} ({result.event_code})",
        f"**Trade Bias:** {trade_bias}",
        f"**Confidence:** {result.confidence:.0%}",
        "",
        "## Release Data",
        "",
        f"- Actual: {result.actual}",
        f"- Forecast: {result.forecast}",
        f"- Previous: {result.previous}",
        f"- Revised Previous: {result.revised_previous}",
        f"- Raw Surprise: {result.raw_surprise}",
        f"- Revision Surprise: {result.revision_surprise}",
        "",
        "## Score",
        "",
        f"- Standardized Surprise: {result.standardized_surprise:+.2f}",
        f"- Directional Score: {result.directional_score:+.2f}",
        f"- Macro Impulse: {result.macro_impulse}",
        "",
        "## Asset Bias",
        "",
        "| Asset Class | Bias |",
        "|---|---|",
    ]
    for asset, bias in result.asset_bias.items():
        lines.append(f"| {asset} | {bias} |")

    lines += [
        "",
        "## Data Warnings",
        "",
    ]
    if result.warnings:
        for warning in result.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")

    lines += [
        "",
        "## Invalidation Conditions",
        "",
        "- Ignore the directional score if official actual data conflicts with the calendar source.",
        "- Downgrade the signal if revisions offset the headline surprise.",
        "- Downgrade the signal if rates and FX do not confirm the expected macro impulse.",
        "- Downgrade the signal if the first 5-15 minute equity reaction fully reverses.",
        "",
    ]
    return "\n".join(lines)


def build_post_release_report(release: MacroRelease) -> str:
    return render_post_release(score_release(release))
