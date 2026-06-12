from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Impact(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Channel(str, Enum):
    GROWTH = "growth"
    INFLATION = "inflation"
    LABOR = "labor"
    CENTRAL_BANK = "central_bank"
    LIQUIDITY = "liquidity"
    CREDIT = "credit"
    CONSUMER = "consumer"
    HOUSING = "housing"
    TRADE = "trade"
    FISCAL = "fiscal"
    CONFIDENCE = "confidence"


class AssetClass(str, Enum):
    EQUITY_INDEX = "equity_index"
    RATES_FRONT_END = "rates_front_end"
    RATES_LONG_END = "rates_long_end"
    FX = "fx"
    USD = "usd"
    COMMODITIES = "commodities"
    VOLATILITY = "volatility"


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    currency: str
    central_bank: str
    primary_equity_proxy: str
    primary_fx_proxy: str
    rates_proxy: str | None = None


@dataclass(frozen=True)
class MacroEventTemplate:
    country_code: str
    event_code: str
    name: str
    impact: Impact
    channels: tuple[Channel, ...]
    higher_is: str
    usual_release_time_local: str | None
    asset_sensitivity: dict[AssetClass, int]
    notes: str = ""


@dataclass
class MacroRelease:
    country_code: str
    event_code: str
    actual: float | None = None
    forecast: float | None = None
    previous: float | None = None
    revised_previous: float | None = None
    unit: str | None = None
    released_at: datetime | None = None
    source: str | None = None
    quality_warnings: list[str] = field(default_factory=list)


@dataclass
class SurpriseResult:
    country_code: str
    event_code: str
    event_name: str
    actual: float | None
    forecast: float | None
    previous: float | None
    revised_previous: float | None
    raw_surprise: float | None
    revision_surprise: float | None
    standardized_surprise: float
    directional_score: float
    macro_impulse: str
    asset_bias: dict[str, str]
    confidence: float
    warnings: list[str]
    details: dict[str, Any] = field(default_factory=dict)
