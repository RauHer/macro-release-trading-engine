from __future__ import annotations

from .models import AssetClass, Channel, Country, Impact, MacroEventTemplate


COUNTRIES: dict[str, Country] = {
    "US": Country("US", "United States", "USD", "Federal Reserve", "SPY/ES", "DXY", "US2Y/US10Y"),
    "EA": Country("EA", "Euro Area", "EUR", "European Central Bank", "FEZ/STOXX", "EURUSD", "DE2Y/DE10Y"),
    "UK": Country("UK", "United Kingdom", "GBP", "Bank of England", "EWU/FTSE", "GBPUSD", "UK2Y/UK10Y"),
    "JP": Country("JP", "Japan", "JPY", "Bank of Japan", "EWJ/NKY", "USDJPY", "JP2Y/JP10Y"),
    "CA": Country("CA", "Canada", "CAD", "Bank of Canada", "EWC/TSX", "USDCAD", "CA2Y/CA10Y"),
    "AU": Country("AU", "Australia", "AUD", "Reserve Bank of Australia", "EWA/ASX", "AUDUSD", "AU2Y/AU10Y"),
    "NZ": Country("NZ", "New Zealand", "NZD", "Reserve Bank of New Zealand", "ENZL/NZX", "NZDUSD", "NZ2Y/NZ10Y"),
    "CH": Country("CH", "Switzerland", "CHF", "Swiss National Bank", "EWL/SMI", "USDCHF", "CH2Y/CH10Y"),
    "SE": Country("SE", "Sweden", "SEK", "Riksbank", "EWD/OMXS", "USDSEK", "SE2Y/SE10Y"),
    "NO": Country("NO", "Norway", "NOK", "Norges Bank", "ENOR/OBX", "USDNOK", "NO2Y/NO10Y"),
}


def _sens(equity: int = 0, front_rates: int = 0, long_rates: int = 0, fx: int = 0, usd: int = 0, vol: int = 0, commodities: int = 0) -> dict[AssetClass, int]:
    return {
        AssetClass.EQUITY_INDEX: equity,
        AssetClass.RATES_FRONT_END: front_rates,
        AssetClass.RATES_LONG_END: long_rates,
        AssetClass.FX: fx,
        AssetClass.USD: usd,
        AssetClass.VOLATILITY: vol,
        AssetClass.COMMODITIES: commodities,
    }


CORE_EVENT_SET: tuple[dict, ...] = (
    {"event_code": "CPI", "name": "Consumer Price Index", "impact": Impact.HIGH, "channels": (Channel.INFLATION, Channel.CENTRAL_BANK), "higher_is": "hawkish_risk_off", "sens": _sens(equity=-2, front_rates=3, long_rates=2, fx=2, usd=2, vol=2)},
    {"event_code": "CORE_CPI", "name": "Core Consumer Price Index", "impact": Impact.HIGH, "channels": (Channel.INFLATION, Channel.CENTRAL_BANK), "higher_is": "hawkish_risk_off", "sens": _sens(equity=-3, front_rates=3, long_rates=2, fx=2, usd=2, vol=2)},
    {"event_code": "PPI", "name": "Producer Price Index", "impact": Impact.MEDIUM, "channels": (Channel.INFLATION,), "higher_is": "hawkish_risk_off", "sens": _sens(equity=-1, front_rates=2, long_rates=1, fx=1, usd=1)},
    {"event_code": "GDP", "name": "Gross Domestic Product", "impact": Impact.HIGH, "channels": (Channel.GROWTH,), "higher_is": "growth_positive", "sens": _sens(equity=2, front_rates=1, long_rates=2, fx=1)},
    {"event_code": "UNEMPLOYMENT", "name": "Unemployment Rate", "impact": Impact.HIGH, "channels": (Channel.LABOR, Channel.GROWTH, Channel.CENTRAL_BANK), "higher_is": "growth_negative_dovish", "sens": _sens(equity=-1, front_rates=-2, long_rates=-1, fx=-1, vol=1)},
    {"event_code": "EMPLOYMENT_CHANGE", "name": "Employment Change", "impact": Impact.HIGH, "channels": (Channel.LABOR, Channel.GROWTH, Channel.CENTRAL_BANK), "higher_is": "growth_positive_hawkish", "sens": _sens(equity=1, front_rates=2, long_rates=1, fx=1)},
    {"event_code": "WAGES", "name": "Wage Growth", "impact": Impact.HIGH, "channels": (Channel.LABOR, Channel.INFLATION, Channel.CENTRAL_BANK), "higher_is": "hawkish_risk_off", "sens": _sens(equity=-2, front_rates=3, long_rates=1, fx=2, vol=1)},
    {"event_code": "RETAIL_SALES", "name": "Retail Sales", "impact": Impact.HIGH, "channels": (Channel.CONSUMER, Channel.GROWTH), "higher_is": "growth_positive", "sens": _sens(equity=2, front_rates=1, long_rates=1, fx=1)},
    {"event_code": "PMI_MFG", "name": "Manufacturing PMI", "impact": Impact.MEDIUM, "channels": (Channel.GROWTH, Channel.CONFIDENCE), "higher_is": "growth_positive", "sens": _sens(equity=1, front_rates=1, long_rates=1, fx=1)},
    {"event_code": "PMI_SERVICES", "name": "Services PMI", "impact": Impact.MEDIUM, "channels": (Channel.GROWTH, Channel.CONFIDENCE), "higher_is": "growth_positive", "sens": _sens(equity=1, front_rates=1, long_rates=1, fx=1)},
    {"event_code": "CENTRAL_BANK_RATE", "name": "Central Bank Policy Rate Decision", "impact": Impact.HIGH, "channels": (Channel.CENTRAL_BANK, Channel.LIQUIDITY), "higher_is": "hawkish_risk_off", "sens": _sens(equity=-3, front_rates=3, long_rates=2, fx=3, vol=2)},
    {"event_code": "CENTRAL_BANK_STATEMENT", "name": "Central Bank Statement / Press Conference", "impact": Impact.HIGH, "channels": (Channel.CENTRAL_BANK,), "higher_is": "contextual", "sens": _sens(equity=-2, front_rates=3, long_rates=2, fx=3, vol=2)},
    {"event_code": "CENTRAL_BANK_MINUTES", "name": "Central Bank Minutes", "impact": Impact.MEDIUM, "channels": (Channel.CENTRAL_BANK,), "higher_is": "contextual", "sens": _sens(equity=-1, front_rates=2, long_rates=1, fx=2)},
    {"event_code": "INDUSTRIAL_PRODUCTION", "name": "Industrial Production", "impact": Impact.MEDIUM, "channels": (Channel.GROWTH,), "higher_is": "growth_positive", "sens": _sens(equity=1, front_rates=1, long_rates=1, fx=1)},
    {"event_code": "TRADE_BALANCE", "name": "Trade Balance", "impact": Impact.MEDIUM, "channels": (Channel.TRADE, Channel.GROWTH), "higher_is": "currency_positive", "sens": _sens(fx=2, equity=1)},
    {"event_code": "HOUSING", "name": "Housing Data", "impact": Impact.MEDIUM, "channels": (Channel.HOUSING, Channel.GROWTH, Channel.CREDIT), "higher_is": "growth_positive", "sens": _sens(equity=1, front_rates=1, long_rates=1)},
    {"event_code": "CONFIDENCE", "name": "Consumer / Business Confidence", "impact": Impact.MEDIUM, "channels": (Channel.CONFIDENCE, Channel.CONSUMER), "higher_is": "growth_positive", "sens": _sens(equity=1, fx=1)},
)


def build_catalog() -> list[MacroEventTemplate]:
    templates: list[MacroEventTemplate] = []
    for country_code in COUNTRIES:
        for item in CORE_EVENT_SET:
            templates.append(
                MacroEventTemplate(
                    country_code=country_code,
                    event_code=item["event_code"],
                    name=item["name"],
                    impact=item["impact"],
                    channels=item["channels"],
                    higher_is=item["higher_is"],
                    usual_release_time_local=None,
                    asset_sensitivity=item["sens"],
                    notes="Generic G10 template; refine source-specific details during official-data adapter phase.",
                )
            )
    return templates


CATALOG = build_catalog()


def list_countries() -> list[Country]:
    return list(COUNTRIES.values())


def find_event(country_code: str, event_code: str) -> MacroEventTemplate:
    cc = country_code.upper()
    ec = event_code.upper()
    for event in CATALOG:
        if event.country_code == cc and event.event_code == ec:
            return event
    raise KeyError(f"Unknown event {cc}/{ec}")


def filter_catalog(country_code: str | None = None, impact: str | None = None) -> list[MacroEventTemplate]:
    events = CATALOG
    if country_code:
        cc = country_code.upper()
        events = [e for e in events if e.country_code == cc]
    if impact:
        imp = impact.lower()
        events = [e for e in events if e.impact.value == imp]
    return events
