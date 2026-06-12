from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SymbolProfile:
    symbol: str
    display_name: str
    asset_class: str
    region: str
    currency: str
    aliases: tuple[str, ...] = ()
    macro_beta: str = "medium"
    rate_sensitivity: str = "medium"
    usd_sensitivity: str = "medium"
    volatility_sensitivity: str = "medium"
    dominant_channels: tuple[str, ...] = ()
    confirmation_instruments: tuple[str, ...] = ()
    explanation: str = ""
    related_symbols: tuple[str, ...] = ()
    notes: str = ""


SYMBOL_PROFILES: dict[str, SymbolProfile] = {
    "NQ": SymbolProfile(
        symbol="NQ",
        display_name="Nasdaq 100 futures / MNQ / QQQ / NAS100 proxy",
        asset_class="equity_index",
        region="US",
        currency="USD",
        aliases=("MNQ", "QQQ", "NAS100", "NDX"),
        macro_beta="high",
        rate_sensitivity="high",
        usd_sensitivity="medium/high",
        volatility_sensitivity="high",
        dominant_channels=("front-end yields", "real yields", "Fed path", "USD liquidity", "mega-cap tech", "semiconductors", "risk appetite"),
        confirmation_instruments=("US2Y", "US10Y", "DXY", "VIX", "QQQ", "SOXX/SMH", "AAPL/MSFT/NVDA", "market breadth"),
        related_symbols=("MNQ", "QQQ", "NAS100", "ES", "RTY", "SOXX", "SMH", "NVDA", "AMD", "AAPL", "MSFT"),
        explanation="NQ is highly sensitive to rates, real yields, liquidity, mega-cap technology, semiconductors, and risk appetite. Inflation and Fed-path shocks often transmit through 2Y/10Y yields, DXY, and growth-equity multiple compression.",
    ),
    "ES": SymbolProfile(
        symbol="ES",
        display_name="S&P 500 futures / MES / SPY / US500 proxy",
        asset_class="equity_index",
        region="US",
        currency="USD",
        aliases=("MES", "SPY", "US500", "SPX"),
        macro_beta="high",
        rate_sensitivity="medium/high",
        usd_sensitivity="medium",
        volatility_sensitivity="high",
        dominant_channels=("broad risk appetite", "earnings discount rate", "Fed path", "USD liquidity", "breadth"),
        confirmation_instruments=("US2Y", "US10Y", "DXY", "VIX", "SPY", "NQ", "RTY", "market breadth"),
        related_symbols=("MES", "SPY", "US500", "SPX", "NQ", "RTY", "DIA"),
        explanation="ES is the broad US equity risk proxy. It is sensitive to growth, inflation, rates, Fed path, liquidity, volatility, and breadth. It is usually less duration-sensitive than NQ but broader and more representative of overall risk appetite.",
    ),
    "RTY": SymbolProfile(
        symbol="RTY",
        display_name="Russell 2000 futures / M2K / IWM proxy",
        asset_class="equity_index",
        region="US",
        currency="USD",
        aliases=("M2K", "IWM", "RUSSELL", "US2000"),
        macro_beta="high",
        rate_sensitivity="high",
        usd_sensitivity="low/medium",
        volatility_sensitivity="high",
        dominant_channels=("credit", "domestic growth", "regional banks", "small-cap risk appetite", "front-end yields"),
        confirmation_instruments=("US2Y", "US10Y", "KRE", "XLF", "HYG", "VIX", "IWM"),
        related_symbols=("M2K", "IWM", "KRE", "XLF", "HYG", "ES", "NQ"),
        explanation="RTY is more domestically cyclical and credit-sensitive than NQ. It can benefit from growth and rate relief, but it is vulnerable when yields rise, credit spreads widen, or regional banks weaken.",
    ),
    "DXY": SymbolProfile(
        symbol="DXY",
        display_name="US Dollar Index",
        asset_class="fx_index",
        region="US",
        currency="USD",
        aliases=("USD", "UUP"),
        macro_beta="high",
        rate_sensitivity="high",
        usd_sensitivity="direct",
        volatility_sensitivity="medium/high",
        dominant_channels=("rate differentials", "Fed path", "risk-off USD demand", "relative growth", "liquidity"),
        confirmation_instruments=("US2Y", "US10Y", "EURUSD", "USDJPY", "gold", "risk assets"),
        related_symbols=("UUP", "EURUSD", "USDJPY", "GBPUSD", "USDCAD", "AUDUSD", "XAUUSD"),
        explanation="DXY is directly sensitive to US data through Fed-path expectations, yield differentials, and global liquidity/risk demand for dollars.",
    ),
    "EURUSD": SymbolProfile(
        symbol="EURUSD",
        display_name="Euro / US Dollar",
        asset_class="fx",
        region="EA/US",
        currency="EURUSD",
        aliases=("6E", "EUR/USD"),
        macro_beta="high",
        rate_sensitivity="high",
        usd_sensitivity="direct",
        volatility_sensitivity="medium",
        dominant_channels=("Fed/ECB rate differential", "growth differential", "inflation differential", "risk appetite", "DXY"),
        confirmation_instruments=("DXY", "US2Y", "DE2Y", "US10Y", "DE10Y", "European equities", "gold"),
        related_symbols=("6E", "DXY", "UUP", "GBPUSD", "USDCHF"),
        explanation="EURUSD responds to relative US versus Euro Area macro data through Fed/ECB path, yield differentials, growth differentials, and broad dollar liquidity.",
    ),
    "NVDA": SymbolProfile(
        symbol="NVDA",
        display_name="NVIDIA",
        asset_class="single_stock",
        region="US",
        currency="USD",
        aliases=("NVIDIA",),
        macro_beta="high",
        rate_sensitivity="high",
        usd_sensitivity="medium",
        volatility_sensitivity="high",
        dominant_channels=("NQ beta", "semiconductor beta", "real yields", "liquidity", "AI growth premium", "risk appetite"),
        confirmation_instruments=("NQ", "QQQ", "SMH", "SOXX", "US2Y", "US10Y", "DXY", "VIX"),
        related_symbols=("NQ", "QQQ", "SMH", "SOXX", "AMD", "AVGO", "MSFT"),
        explanation="NVDA is macro-sensitive through NQ/semiconductor beta, real yields, liquidity, USD, and risk appetite, but idiosyncratic AI, earnings, guidance, product, and positioning risk can overpower macro impulses.",
    ),
}


def get_symbol_profile(symbol: str) -> SymbolProfile:
    key = symbol.upper().strip()
    if key in SYMBOL_PROFILES:
        return SYMBOL_PROFILES[key]
    for profile in SYMBOL_PROFILES.values():
        if key in {alias.upper() for alias in profile.aliases}:
            return profile
    return SymbolProfile(
        symbol=key,
        display_name=key,
        asset_class="unknown",
        region="unknown",
        currency="unknown",
        macro_beta="unknown",
        rate_sensitivity="unknown",
        usd_sensitivity="unknown",
        volatility_sensitivity="unknown",
        dominant_channels=("unknown",),
        confirmation_instruments=("price reaction", "volume", "related market proxies"),
        explanation="No dedicated symbol profile exists yet. Treat this as a generic macro-sensitive symbol and rely more heavily on observed price confirmation.",
        notes="Add a dedicated profile for this symbol if it becomes part of the regular trading universe.",
    )
