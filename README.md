# Macro Release Trading Engine

A Python project for building a G10 macroeconomic news and release workflow for trading. The engine collects scheduled macro events, normalizes releases across countries, scores actual-vs-consensus surprise, classifies the macro transmission channel, and produces pre-release and post-release trading reports.

## Core Philosophy

Markets do not move because a number is simply "good" or "bad." They move because new information changes expectations around growth, inflation, labor-market strength, central-bank policy path, liquidity, risk appetite, currency pressure, and rates pressure.

```text
calendar -> expectation -> actual -> revision -> surprise -> regime -> rates/FX/equity confirmation -> trade bias
```

## G10 Coverage

The initial catalog covers:

- United States
- Euro Area
- United Kingdom
- Japan
- Canada
- Australia
- New Zealand
- Switzerland
- Sweden
- Norway

## What This Version Includes

- G10 event catalog
- event importance classification
- macro-channel mapping
- expected asset sensitivity model
- manual forecast/actual entry support
- public-source adapter interface
- surprise scoring
- revision scoring
- market-confirmation scoring hooks
- pre-release report generation
- post-release report generation
- command-line interface
- test-ready project layout

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## CLI Usage

```bash
python -m macro_engine.cli countries
python -m macro_engine.cli catalog
python -m macro_engine.cli catalog --impact high
python -m macro_engine.cli pre --country US --event CPI
python -m macro_engine.cli score --country US --event CPI --actual 3.4 --forecast 3.2 --previous 3.1
python -m macro_engine.cli report --country US --event CPI --actual 3.4 --forecast 3.2 --previous 3.1
```

## Development Roadmap

### Phase 1 — G10 Catalog and Manual Scoring
Completed in the initial scaffold.

### Phase 2 — Calendar Ingestion
Add adapters for public economic calendar pages. These should be isolated modules so one broken website cannot break the whole engine.

### Phase 3 — Official Actual-Data Fetchers
Add official-source fetchers by country and agency.

### Phase 4 — Market Reaction Layer
Add market reaction measurement across equity index futures/ETFs, rates, FX, USD proxies, gold/crude, and volatility proxies.

### Phase 5 — Event Study and Backtest
Measure historical reaction windows: 1m, 5m, 15m, 60m, session close, and overnight continuation.

### Phase 6 — TradingView Export
Export daily macro state as CSV/JSON for TradingView workflows.

## Disclaimer

This project is for research, education, and workflow support. It is not financial advice and does not place trades.
