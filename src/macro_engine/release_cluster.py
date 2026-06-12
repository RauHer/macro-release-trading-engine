from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Iterable

from .catalog import find_event
from .models import Channel, MacroRelease
from .release_assessment import ReleaseAssessment, assess_release, render_release_assessment


@dataclass
class ReleaseClusterAssessment:
    cluster_name: str
    cluster_type: str
    country_code: str
    assessments: list[ReleaseAssessment]
    alignment: str
    net_macro_impulse: str
    rates_impulse: str
    usd_fx_impulse: str
    equity_impulse: str
    confidence_label: str
    conflict_warnings: list[str] = field(default_factory=list)


INFLATION_EVENTS = {"CPI", "CORE_CPI", "PPI", "INFLATION_EXPECTATIONS", "WAGES"}
LABOR_EVENTS = {"EMPLOYMENT_CHANGE", "UNEMPLOYMENT", "JOBLESS_CLAIMS", "WAGES"}
GROWTH_EVENTS = {"GDP", "RETAIL_SALES", "INDUSTRIAL_PRODUCTION", "CONFIDENCE", "TOURISM"}
PMI_EVENTS = {"PMI_MFG", "PMI_SERVICES"}
HOUSING_EVENTS = {"HOUSING", "BUILDING_PERMITS"}
CENTRAL_BANK_EVENTS = {"CENTRAL_BANK_RATE", "CENTRAL_BANK_STATEMENT", "CENTRAL_BANK_MINUTES"}
ENERGY_EVENTS = {"ENERGY_INVENTORIES"}
AUCTION_EVENTS = {"BOND_AUCTION"}


def _cluster_family(event_codes: set[str]) -> tuple[str, str]:
    if event_codes & CENTRAL_BANK_EVENTS:
        return "Central Bank Policy Cluster", "central_bank"
    if event_codes & INFLATION_EVENTS and not (event_codes & LABOR_EVENTS - {"WAGES"}):
        return "Inflation Cluster", "inflation"
    if event_codes & LABOR_EVENTS:
        return "Labor Market Cluster", "labor"
    if event_codes & PMI_EVENTS:
        return "PMI / Survey Cluster", "pmi_survey"
    if event_codes & HOUSING_EVENTS:
        return "Housing / Credit Cluster", "housing_credit"
    if event_codes & ENERGY_EVENTS:
        return "Energy / Inventory Cluster", "energy_inventory"
    if event_codes & AUCTION_EVENTS:
        return "Auction / Rates-Supply Cluster", "auction_rates_supply"
    if event_codes & GROWTH_EVENTS:
        return "Growth / Consumption Cluster", "growth_consumption"
    return "Mixed Macro Cluster", "mixed"


def _direction_bucket(a: ReleaseAssessment) -> str:
    text = f"{a.trader_interpretation} {a.first_macro_read}".lower()
    if any(x in text for x in ["hotter", "hawkish", "larger inventory build", "higher clearing yield"]):
        return "hawkish_or_risk_negative"
    if any(x in text for x in ["cooler", "dovish", "smaller inventory build", "larger draw", "lower clearing yield"]):
        return "dovish_or_risk_supportive"
    if any(x in text for x in ["stronger", "growth-positive", "stronger labor"]):
        return "growth_positive"
    if any(x in text for x in ["weaker", "growth-negative", "weaker labor"]):
        return "growth_negative"
    return "neutral_or_contextual"


def _count_buckets(assessments: Iterable[ReleaseAssessment]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for assessment in assessments:
        bucket = _direction_bucket(assessment)
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _alignment_for(cluster_type: str, assessments: list[ReleaseAssessment]) -> tuple[str, str, list[str]]:
    counts = _count_buckets(assessments)
    warnings: list[str] = []
    hawkish = counts.get("hawkish_or_risk_negative", 0)
    dovish = counts.get("dovish_or_risk_supportive", 0)
    growth_pos = counts.get("growth_positive", 0)
    growth_neg = counts.get("growth_negative", 0)
    contextual = counts.get("neutral_or_contextual", 0)

    if cluster_type == "inflation":
        if hawkish > 0 and dovish == 0:
            return "aligned_hawkish", "Net hawkish inflation impulse; rates-positive, USD-positive, duration-equity negative if confirmed.", warnings
        if dovish > 0 and hawkish == 0:
            return "aligned_dovish", "Net dovish inflation impulse; rates-negative and duration-equity supportive if growth scare does not dominate.", warnings
        if hawkish and dovish:
            warnings.append("Headline/core or related inflation releases conflict; wait for rates/USD confirmation.")
            return "mixed_inflation", "Mixed inflation impulse; market confirmation should dominate.", warnings

    if cluster_type == "labor":
        if hawkish and growth_pos and not growth_neg:
            return "aligned_hawkish_labor", "Hot/tight labor impulse; front-end yields and USD should rise if market prices Fed-path pressure.", warnings
        if growth_neg and not hawkish and not growth_pos:
            return "growth_negative_labor", "Labor deterioration impulse; rates may fall, but equities can sell off if recession fear dominates.", warnings
        if hawkish or growth_pos or growth_neg or dovish:
            warnings.append("Labor details are mixed; payrolls, unemployment, wages, participation, and revisions must be weighted together.")
            return "mixed_labor", "Mixed labor impulse; symbol direction is conditional on rates/USD and risk reaction.", warnings

    if cluster_type == "central_bank":
        if hawkish and not dovish:
            return "aligned_hawkish_policy", "Hawkish policy impulse; bearish duration assets if front-end yields confirm.", warnings
        if dovish and not hawkish:
            return "aligned_dovish_policy", "Dovish policy impulse; supportive risk impulse unless interpreted as growth panic.", warnings
        warnings.append("Policy decision, statement, or guidance may conflict; market reaction should dominate.")
        return "mixed_policy", "Mixed policy impulse; wait for front-end yields, FX, and equities to resolve.", warnings

    if cluster_type in {"growth_consumption", "pmi_survey", "housing_credit"}:
        if growth_pos and not growth_neg and not hawkish:
            return "aligned_growth_positive", "Growth-positive impulse; risk-positive unless rates pressure dominates.", warnings
        if growth_neg and not growth_pos:
            return "aligned_growth_negative", "Growth-negative impulse; risk impact depends on whether the market sees rate relief or recession risk.", warnings
        if growth_pos and hawkish:
            warnings.append("Growth strength may be equity-positive or rates-negative depending on inflation/Fed-path regime.")
            return "growth_positive_but_rates_sensitive", "Growth-positive but potentially rates-negative for duration equities.", warnings
        return "mixed_growth", "Mixed growth impulse; wait for equity breadth and rates confirmation.", warnings

    if cluster_type == "energy_inventory":
        if dovish and not hawkish:
            return "commodity_supportive_inventory", "Inventory-flow impulse may support energy if seasonal/demand context confirms.", warnings
        if hawkish and not dovish:
            return "commodity_negative_inventory", "Inventory-flow impulse may pressure energy if seasonal/demand context confirms.", warnings
        return "mixed_inventory", "Inventory signal is mixed or incomplete; compare against seasonal expectations and commodity reaction.", warnings

    if cluster_type == "auction_rates_supply":
        if hawkish and not dovish:
            return "weak_auction_rates_up", "Auction signal may pressure bonds and lift yields; duration equities vulnerable if rates confirm.", warnings
        if dovish and not hawkish:
            return "strong_auction_rates_down", "Auction signal may support bonds and pressure yields; duration equities supported if rates confirm.", warnings
        return "mixed_auction", "Auction signal incomplete; tail, bid-to-cover, and bidder composition are required for high confidence.", warnings

    if contextual:
        warnings.append("One or more releases are contextual or lack enough numerical information for a clean cluster score.")
    return "mixed_or_contextual", "Mixed or contextual macro impulse; require market confirmation before trading.", warnings


def _impulses(alignment: str) -> tuple[str, str, str]:
    if "hawkish" in alignment or "rates_up" in alignment:
        return (
            "Rates-positive: front-end and/or real yields should rise if the market agrees.",
            "USD-positive if rate differentials confirm.",
            "Bearish for duration-sensitive equities if yields/USD confirm.",
        )
    if "dovish" in alignment or "rates_down" in alignment:
        return (
            "Rates-negative: yields should fall if the market agrees.",
            "USD-negative unless risk-off dollar demand dominates.",
            "Supportive for duration-sensitive equities if growth-scare conditions do not dominate.",
        )
    if "growth_positive" in alignment:
        return (
            "Rates may rise if growth strength affects central-bank expectations.",
            "Local currency can strengthen if growth improves rate differentials.",
            "Risk-positive unless rates pressure dominates.",
        )
    if "growth_negative" in alignment:
        return (
            "Rates may fall on growth weakness.",
            "FX impact depends on relative growth and risk sentiment.",
            "Equity impact is conditional: rate relief can help, recession fear can hurt.",
        )
    return (
        "Rates impulse unclear; wait for yield confirmation.",
        "USD/FX impulse unclear; wait for FX confirmation.",
        "Equity impulse unclear; wait for price, breadth, and volatility confirmation.",
    )


def assess_release_cluster(releases: list[MacroRelease]) -> ReleaseClusterAssessment:
    if not releases:
        raise ValueError("Cannot assess an empty release cluster.")
    assessments = [assess_release(r) for r in releases]
    country = releases[0].country_code.upper()
    event_codes = {r.event_code.upper() for r in releases}
    cluster_name, cluster_type = _cluster_family(event_codes)
    alignment, net_macro_impulse, warnings = _alignment_for(cluster_type, assessments)
    rates_impulse, usd_fx_impulse, equity_impulse = _impulses(alignment)

    if alignment.startswith("aligned") or alignment in {"commodity_supportive_inventory", "commodity_negative_inventory", "weak_auction_rates_up", "strong_auction_rates_down"}:
        confidence = "moderate/high, pending market confirmation"
    elif "mixed" in alignment:
        confidence = "moderate/low because the cluster is mixed"
    else:
        confidence = "conditional"

    return ReleaseClusterAssessment(
        cluster_name=cluster_name,
        cluster_type=cluster_type,
        country_code=country,
        assessments=assessments,
        alignment=alignment,
        net_macro_impulse=net_macro_impulse,
        rates_impulse=rates_impulse,
        usd_fx_impulse=usd_fx_impulse,
        equity_impulse=equity_impulse,
        confidence_label=confidence,
        conflict_warnings=warnings,
    )


def group_releases_by_time_window(releases: list[MacroRelease], window_minutes: int = 5) -> list[list[MacroRelease]]:
    dated = [r for r in releases if r.released_at is not None]
    undated = [r for r in releases if r.released_at is None]
    clusters: list[list[MacroRelease]] = []
    for release in sorted(dated, key=lambda r: r.released_at):
        placed = False
        for cluster in clusters:
            anchor = cluster[0].released_at
            if anchor and release.released_at and abs(release.released_at - anchor) <= timedelta(minutes=window_minutes):
                cluster.append(release)
                placed = True
                break
        if not placed:
            clusters.append([release])
    clusters.extend([[r] for r in undated])
    return clusters


def render_cluster_assessment(cluster: ReleaseClusterAssessment) -> str:
    lines = [
        f"Release Cluster: {cluster.cluster_name}",
        f"Country: {cluster.country_code}",
        f"Cluster type: {cluster.cluster_type}",
        f"Events included: {', '.join(a.event_code for a in cluster.assessments)}",
        "",
        "Cluster Assessment:",
    ]
    for assessment in cluster.assessments:
        lines.extend(
            [
                f"- {assessment.event_code}: {assessment.mathematical_comparison} / {assessment.trader_interpretation}",
                f"  Assessment type: {assessment.assessment_type.value}; Confidence: {assessment.confidence_label}",
            ]
        )
    lines.extend(
        [
            "",
            "Net Cluster Impulse:",
            f"- Alignment: {cluster.alignment}",
            f"- Macro read: {cluster.net_macro_impulse}",
            f"- Rates impulse: {cluster.rates_impulse}",
            f"- USD/FX impulse: {cluster.usd_fx_impulse}",
            f"- Equity impulse: {cluster.equity_impulse}",
            f"- Confidence: {cluster.confidence_label}",
        ]
    )
    if cluster.conflict_warnings:
        lines.append("- Conflict warnings:")
        for warning in cluster.conflict_warnings:
            lines.append(f"  - {warning}")
    lines.extend(["", "Individual Release Detail:"])
    for assessment in cluster.assessments:
        lines.append("")
        lines.append(render_release_assessment(assessment))
    return "\n".join(lines)
