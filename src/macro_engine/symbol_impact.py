from __future__ import annotations

from dataclasses import dataclass, field

from .models import MacroRelease
from .release_assessment import ReleaseAssessment, assess_release, render_release_assessment
from .release_cluster import ReleaseClusterAssessment, assess_release_cluster, render_cluster_assessment
from .symbol_profiles import SymbolProfile, get_symbol_profile


@dataclass
class SymbolImpactReport:
    symbol: str
    display_name: str
    direction: str
    confidence: str
    trade_posture: str
    do_not_chase_condition: str
    confirmation_checklist: list[str]
    invalidation_conditions: list[str]
    macro_regime_note: str
    symbol_explanation: str
    source_type: str
    release_assessment: ReleaseAssessment | None = None
    cluster_assessment: ReleaseClusterAssessment | None = None
    educational_note: str = ""


def _symbol_family(profile: SymbolProfile) -> str:
    if profile.symbol in {"NQ", "ES", "RTY"} or profile.asset_class == "equity_index":
        return "equity_index"
    if profile.asset_class == "single_stock":
        return "single_stock"
    if profile.asset_class in {"fx", "fx_index"}:
        return "fx"
    return profile.asset_class


def _direction_from_text(text: str, profile: SymbolProfile) -> tuple[str, str, str, str]:
    lower = text.lower()
    family = _symbol_family(profile)

    if family in {"equity_index", "single_stock"}:
        if any(x in lower for x in ["hawkish", "hotter", "rates-positive", "duration-equity negative", "weak_auction_rates_up"]):
            return (
                f"Bearish {profile.symbol}",
                "Moderate/high if rates, USD, and volatility confirm",
                "Short-biased continuation or wait-for-confirmation",
                f"If {profile.symbol} drops but 2Y yield, 10Y yield, and DXY fail to confirm, downgrade to wait/no-trade.",
            )
        if any(x in lower for x in ["dovish", "cooler", "rates-negative", "duration-equity supportive", "strong_auction_rates_down"]):
            return (
                f"Bullish {profile.symbol}",
                "Moderate/high if yields fall, USD weakens, and risk confirms",
                "Long-biased continuation or wait-for-confirmation",
                f"If {profile.symbol} rallies but yields, USD, breadth, or volatility do not confirm, downgrade to wait/no-trade.",
            )
        if "growth-negative" in lower or "labor deterioration" in lower:
            return (
                f"Conditional {profile.symbol}",
                "Moderate/low because weak growth can be rate-relief bullish or recession-scare bearish",
                "Wait for confirmation",
                f"Do not force direction until {profile.symbol}, yields, volatility, and breadth agree.",
            )
        if "growth-positive" in lower:
            return (
                f"Conditional bullish {profile.symbol}",
                "Moderate if growth is rewarded and yields do not rise aggressively",
                "Long-biased only if rates pressure stays contained",
                f"If yields spike or DXY firms aggressively, downgrade {profile.symbol} to wait/no-trade.",
            )

    if family == "fx":
        if any(x in lower for x in ["hawkish", "hotter", "rates-positive", "usd-positive"]):
            if profile.symbol == "DXY":
                return ("Bullish DXY", "Moderate/high if US yields confirm", "Long-biased USD continuation", "If US yields fade, downgrade the DXY bullish read.")
            if "USD" in profile.currency and profile.symbol.endswith("USD"):
                return (f"Bearish {profile.symbol}", "Moderate if USD strengthens on rate differentials", "Short-biased only if DXY/yields confirm", "If DXY fades, downgrade to wait/no-trade.")
            return (f"USD-positive pressure for {profile.symbol}", "Conditional", "Trade only after FX confirmation", "If rate differentials fail to confirm, stand aside.")
        if any(x in lower for x in ["dovish", "cooler", "rates-negative", "usd-negative"]):
            if profile.symbol == "DXY":
                return ("Bearish DXY", "Moderate/high if US yields fall", "Short-biased USD continuation", "If US yields rebound, downgrade the DXY bearish read.")
            if "USD" in profile.currency and profile.symbol.endswith("USD"):
                return (f"Bullish {profile.symbol}", "Moderate if USD weakens on rate differentials", "Long-biased only if DXY/yields confirm", "If DXY firms, downgrade to wait/no-trade.")
            return (f"USD-negative pressure for {profile.symbol}", "Conditional", "Trade only after FX confirmation", "If rate differentials fail to confirm, stand aside.")

    return (
        f"Wait for confirmation in {profile.symbol}",
        "Low/conditional because the symbol profile or macro impulse is not decisive",
        "Wait-for-confirmation",
        "No trade if the macro read and price reaction conflict.",
    )


def _confirmation(profile: SymbolProfile) -> list[str]:
    base = [f"{profile.symbol} holds the release-direction move versus the pre-release level"]
    base.extend(profile.confirmation_instruments)
    base.append("volatility and breadth agree with the intended trade direction")
    return list(dict.fromkeys(base))


def _invalidation(profile: SymbolProfile) -> list[str]:
    family = _symbol_family(profile)
    if family in {"equity_index", "single_stock"}:
        return [
            "2Y yield fails to confirm the rate-path interpretation",
            "10Y yield or real yields reverse against the expected direction",
            "DXY fails to confirm or reverses sharply",
            f"{profile.symbol} reclaims the pre-release level after an initial bearish move, or loses it after an initial bullish move",
            "VIX/volatility reaction contradicts the trade",
            "sector leadership, breadth, or related proxies disagree",
        ]
    if family == "fx":
        return [
            "rate differentials fail to confirm",
            "DXY moves against the expected direction",
            "the pair reverses through the pre-release level",
            "risk sentiment overwhelms the rate-differential read",
        ]
    return [
        "price action reverses the release-direction move",
        "related proxy markets disagree",
        "volume/volatility does not confirm",
        "the release interpretation and market reaction conflict",
    ]


def _regime_note(direction: str) -> str:
    if "Bearish" in direction:
        return "In a sticky-inflation, higher-for-longer, or rising-real-yield regime, bearish duration-equity reads deserve more weight. In a liquidity-driven squeeze regime, bearish headline reads require stronger rates/USD confirmation because the first move can fade."
    if "Bullish" in direction:
        return "In a disinflationary soft-landing or liquidity-supportive regime, bullish duration-equity reads deserve more weight. In a growth-scare regime, cooler/weaker data can still become equity-bearish if the market shifts from rate relief to recession fear."
    return "The current macro regime determines whether the release is traded as rate relief, growth risk, inflation pressure, or liquidity stress. Because this read is conditional, market confirmation should dominate."


def assess_symbol_impact_for_release(symbol: str, release: MacroRelease) -> SymbolImpactReport:
    profile = get_symbol_profile(symbol)
    assessment = assess_release(release)
    text = f"{assessment.trader_interpretation} {assessment.first_macro_read} {assessment.mathematical_comparison}"
    direction, confidence, posture, do_not_chase = _direction_from_text(text, profile)
    return SymbolImpactReport(
        symbol=profile.symbol,
        display_name=profile.display_name,
        direction=direction,
        confidence=confidence,
        trade_posture=posture,
        do_not_chase_condition=do_not_chase,
        confirmation_checklist=_confirmation(profile),
        invalidation_conditions=_invalidation(profile),
        macro_regime_note=_regime_note(direction),
        symbol_explanation=profile.explanation,
        source_type="single_release",
        release_assessment=assessment,
        educational_note="The directional read is a trading hypothesis, not a command. The release assessment defines the macro impulse; the symbol profile defines likely transmission; confirmation/invalidation decides whether the trade is valid.",
    )


def assess_symbol_impact_for_cluster(symbol: str, releases: list[MacroRelease]) -> SymbolImpactReport:
    profile = get_symbol_profile(symbol)
    cluster = assess_release_cluster(releases)
    text = f"{cluster.alignment} {cluster.net_macro_impulse} {cluster.rates_impulse} {cluster.usd_fx_impulse} {cluster.equity_impulse}"
    direction, confidence, posture, do_not_chase = _direction_from_text(text, profile)
    if "mixed" in cluster.alignment:
        if "Bearish" in direction:
            direction = direction.replace("Bearish", "Conditional bearish")
        elif "Bullish" in direction:
            direction = direction.replace("Bullish", "Conditional bullish")
        elif "Wait" not in direction and "Conditional" not in direction:
            direction = f"Conditional {direction}"
        confidence = "Moderate/low because the cluster is mixed; market confirmation is required"
        posture = "Wait-for-confirmation or trade only after rates/USD/risk resolve the conflict"
    return SymbolImpactReport(
        symbol=profile.symbol,
        display_name=profile.display_name,
        direction=direction,
        confidence=confidence,
        trade_posture=posture,
        do_not_chase_condition=do_not_chase,
        confirmation_checklist=_confirmation(profile),
        invalidation_conditions=_invalidation(profile),
        macro_regime_note=_regime_note(direction),
        symbol_explanation=profile.explanation,
        source_type="release_cluster",
        cluster_assessment=cluster,
        educational_note="Cluster reads should be weighted by alignment. Aligned clusters can support cleaner directional trades. Mixed clusters require stricter confirmation and faster downgrades to wait/no-trade.",
    )


def render_symbol_impact(report: SymbolImpactReport) -> str:
    lines = [
        f"Symbol: {report.symbol} — {report.display_name}",
        "",
        "Final Trade Direction For Queried Symbol:",
        f"- Direction: {report.direction}",
        f"- Confidence: {report.confidence}",
        f"- Trade posture: {report.trade_posture}",
        f"- Do not chase condition: {report.do_not_chase_condition}",
        "",
    ]

    if report.release_assessment is not None:
        lines.append(render_release_assessment(report.release_assessment))
        lines.append("")
    if report.cluster_assessment is not None:
        lines.append(render_cluster_assessment(report.cluster_assessment))
        lines.append("")

    lines.extend(
        [
            "Macro-Regime / Environment Assay:",
            report.macro_regime_note,
            "",
            "Symbol-Specific Explanation:",
            report.symbol_explanation,
            "",
            "Confirmation Checklist:",
        ]
    )
    for item in report.confirmation_checklist:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Invalidation / No-Trade Conditions:")
    for item in report.invalidation_conditions:
        lines.append(f"- {item}")
    lines.extend(["", "Educational Note:", report.educational_note])
    return "\n".join(lines)
