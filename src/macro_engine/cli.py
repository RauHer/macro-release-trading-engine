from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date

from .calendar_sources import PUBLIC_CALENDAR_PRESETS, MultiSourceCalendar, PresetCalendarSource, build_preset_sources
from .catalog import filter_catalog, list_countries
from .diagnostics import run_calendar_diagnostics
from .models import MacroRelease
from .release_assessment import assess_release, render_release_assessment
from .release_cluster import assess_release_cluster, render_cluster_assessment
from .reports import render_post_release, render_pre_release
from .scoring import classify_trade_bias, score_release
from .sources import GenericHTMLCalendarSource, ManualCalendarCSVSource
from .storage import save_calendar_events


def _add_release_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--country", required=True, help="G10 country code, e.g. US, EA, UK, JP, CA, AU, NZ, CH, SE, NO")
    parser.add_argument("--event", required=True, help="Event code, e.g. CPI, GDP, CENTRAL_BANK_RATE")
    parser.add_argument("--actual", type=float, default=None)
    parser.add_argument("--forecast", type=float, default=None)
    parser.add_argument("--previous", type=float, default=None)
    parser.add_argument("--revised-previous", type=float, default=None)
    parser.add_argument("--json", action="store_true", help="Return JSON output")


def _parse_date(value: str | None) -> date:
    return date.fromisoformat(value) if value else date.today()


def _parse_sources(value: str | None) -> list[str] | None:
    return [x.strip() for x in value.split(",") if x.strip()] if value else None


def _parse_cluster_events(value: str) -> list[str]:
    return [x.strip().upper() for x in value.split(",") if x.strip()]


def _parse_cluster_values(value: str | None, count: int) -> list[float | None]:
    if value is None:
        return [None] * count
    raw = [x.strip() for x in value.split(",")]
    values: list[float | None] = []
    for item in raw:
        if item == "" or item.lower() in {"none", "na", "n/a", "null"}:
            values.append(None)
        else:
            values.append(float(item))
    if len(values) != count:
        raise SystemExit(f"Expected {count} comma-separated values, got {len(values)}")
    return values


def cmd_countries(_: argparse.Namespace) -> None:
    for c in list_countries():
        print(f"{c.code:<2}  {c.name:<16} {c.currency:<3}  {c.central_bank}")


def cmd_sources(_: argparse.Namespace) -> None:
    for key, preset in PUBLIC_CALENDAR_PRESETS.items():
        print(f"{key:<18} {preset.name}")
        print(f"{'':<18} {preset.url}")
        print(f"{'':<18} Adapter: {preset.adapter}")
        print(f"{'':<18} {preset.notes}")


def cmd_catalog(args: argparse.Namespace) -> None:
    events = filter_catalog(country_code=args.country, impact=args.impact)
    for e in events:
        channels = ",".join(c.value for c in e.channels)
        print(f"{e.country_code:<2} {e.event_code:<24} {e.impact.value:<6} {channels:<38} {e.name}")


def cmd_pre(args: argparse.Namespace) -> None:
    print(render_pre_release(args.country, args.event))


def _filter_calendar_events(events, args):
    if args.country:
        events = [e for e in events if e.country_code == args.country.upper()]
    if args.impact:
        events = [e for e in events if e.impact.lower() == args.impact.lower()]
    return events


def _preview_calendar(events, preview: int) -> None:
    for e in events[:preview]:
        when = e.scheduled_at.isoformat() if e.scheduled_at else "unscheduled"
        print(f"{when:<25} {e.country_code:<2} {e.event_code:<24} {e.impact:<6} {e.name} [{e.source}]")


def cmd_calendar_import(args: argparse.Namespace) -> None:
    target = _parse_date(args.date)
    if args.csv:
        source = ManualCalendarCSVSource(args.csv)
    elif args.url:
        source = GenericHTMLCalendarSource(args.url, source_name=args.source_name or "generic_html")
    elif args.preset:
        source = PresetCalendarSource(args.preset)
    else:
        raise SystemExit("calendar-import requires --csv, --url, or --preset")

    events = _filter_calendar_events(source.fetch_calendar(target), args)
    out_path = save_calendar_events(events, target, label=args.label or source.source_name)
    print(f"Imported {len(events)} events for {target} -> {out_path}")
    _preview_calendar(events, args.preview)


def cmd_calendar_multi_import(args: argparse.Namespace) -> None:
    target = _parse_date(args.date)
    keys = _parse_sources(args.sources)
    multi = MultiSourceCalendar(build_preset_sources(keys))
    result = multi.fetch_calendar_result(target)
    events = _filter_calendar_events(result.events, args)
    out_path = save_calendar_events(events, target, label=args.label or "multi_source")
    print(f"Imported {len(events)} deduped events for {target} -> {out_path}")
    print("\nSource attempts:")
    for attempt in result.attempts:
        status = "OK" if attempt.ok else "FAIL"
        detail = f"{attempt.events} events" if attempt.ok else attempt.error
        print(f"- {attempt.source:<18} {status:<4} {detail}")
    print("\nPreview:")
    _preview_calendar(events, args.preview)


def cmd_calendar_diagnostics(args: argparse.Namespace) -> None:
    target = _parse_date(args.date)
    path, attempts, deduped_events = run_calendar_diagnostics(target, _parse_sources(args.sources))
    print(f"Diagnostics saved -> {path}")
    print(f"Deduped events: {deduped_events}")
    for attempt in attempts:
        status = "OK" if attempt.ok else "FAIL"
        detail = f"{attempt.events} events" if attempt.ok else attempt.error
        print(f"- {attempt.source:<18} {status:<4} {detail}")


def cmd_calendar_view(args: argparse.Namespace) -> None:
    target = _parse_date(args.date)
    events = filter_catalog(country_code=args.country, impact=args.impact)
    print(f"# Catalog Calendar View — {target}")
    for e in events:
        print(f"{e.country_code:<2} {e.event_code:<24} {e.impact.value:<6} {e.name}")


def _release_from_args(args: argparse.Namespace) -> MacroRelease:
    return MacroRelease(
        country_code=args.country.upper(),
        event_code=args.event.upper(),
        actual=args.actual,
        forecast=args.forecast,
        previous=args.previous,
        revised_previous=args.revised_previous,
        source="manual_cli",
    )


def cmd_assess_release(args: argparse.Namespace) -> None:
    assessment = assess_release(_release_from_args(args))
    if args.json:
        print(json.dumps(asdict(assessment), indent=2, default=str))
        return
    print(render_release_assessment(assessment))


def cmd_assess_cluster(args: argparse.Namespace) -> None:
    events = _parse_cluster_events(args.events)
    actuals = _parse_cluster_values(args.actuals, len(events))
    forecasts = _parse_cluster_values(args.forecasts, len(events))
    previous_values = _parse_cluster_values(args.previous, len(events))
    releases = [
        MacroRelease(
            country_code=args.country.upper(),
            event_code=event_code,
            actual=actuals[i],
            forecast=forecasts[i],
            previous=previous_values[i],
            source="manual_cli_cluster",
        )
        for i, event_code in enumerate(events)
    ]
    cluster = assess_release_cluster(releases)
    if args.json:
        print(json.dumps(asdict(cluster), indent=2, default=str))
        return
    print(render_cluster_assessment(cluster))


def cmd_score(args: argparse.Namespace) -> None:
    result = score_release(_release_from_args(args))
    if args.json:
        payload = asdict(result)
        payload["trade_bias"] = classify_trade_bias(result)
        print(json.dumps(payload, indent=2, default=str))
        return

    print(f"Event: {result.country_code}/{result.event_code} — {result.event_name}")
    print(f"Actual: {result.actual} | Forecast: {result.forecast} | Previous: {result.previous}")
    print(f"Raw surprise: {result.raw_surprise}")
    print(f"Standardized surprise: {result.standardized_surprise:+.2f}")
    print(f"Directional score: {result.directional_score:+.2f}")
    print(f"Macro impulse: {result.macro_impulse}")
    print(f"Trade bias: {classify_trade_bias(result)}")
    print(f"Confidence: {result.confidence:.0%}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")


def cmd_report(args: argparse.Namespace) -> None:
    result = score_release(_release_from_args(args))
    print(render_post_release(result))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="G10 macro release trading intelligence engine")
    sub = parser.add_subparsers(dest="command", required=True)

    p_countries = sub.add_parser("countries", help="List supported G10 countries")
    p_countries.set_defaults(func=cmd_countries)

    p_sources = sub.add_parser("sources", help="List built-in public calendar source presets")
    p_sources.set_defaults(func=cmd_sources)

    p_catalog = sub.add_parser("catalog", help="List macro event catalog")
    p_catalog.add_argument("--country", default=None)
    p_catalog.add_argument("--impact", choices=["high", "medium", "low"], default=None)
    p_catalog.set_defaults(func=cmd_catalog)

    p_calendar_view = sub.add_parser("calendar-view", help="View catalog events by country/impact")
    p_calendar_view.add_argument("--date", default=None)
    p_calendar_view.add_argument("--country", default=None)
    p_calendar_view.add_argument("--impact", choices=["high", "medium", "low"], default=None)
    p_calendar_view.set_defaults(func=cmd_calendar_view)

    p_calendar_import = sub.add_parser("calendar-import", help="Import economic calendar events from CSV, URL, or named preset")
    p_calendar_import.add_argument("--date", default=None, help="Target date YYYY-MM-DD; default today")
    p_calendar_import.add_argument("--csv", default=None, help="Normalized CSV calendar file")
    p_calendar_import.add_argument("--url", default=None, help="Public HTML page containing ordinary calendar tables")
    p_calendar_import.add_argument("--preset", choices=sorted(PUBLIC_CALENDAR_PRESETS), default=None)
    p_calendar_import.add_argument("--source-name", default=None)
    p_calendar_import.add_argument("--label", default=None, help="Output file label")
    p_calendar_import.add_argument("--country", default=None)
    p_calendar_import.add_argument("--impact", choices=["high", "medium", "low"], default=None)
    p_calendar_import.add_argument("--preview", type=int, default=25)
    p_calendar_import.set_defaults(func=cmd_calendar_import)

    p_multi = sub.add_parser("calendar-multi-import", help="Try several public calendar presets and dedupe results")
    p_multi.add_argument("--date", default=None, help="Target date YYYY-MM-DD; default today")
    p_multi.add_argument("--sources", default=None, help="Comma-separated preset keys; default all presets")
    p_multi.add_argument("--label", default=None)
    p_multi.add_argument("--country", default=None)
    p_multi.add_argument("--impact", choices=["high", "medium", "low"], default=None)
    p_multi.add_argument("--preview", type=int, default=25)
    p_multi.set_defaults(func=cmd_calendar_multi_import)

    p_diag = sub.add_parser("calendar-diagnostics", help="Probe calendar sources and write a diagnostics report")
    p_diag.add_argument("--date", default=None, help="Target date YYYY-MM-DD; default today")
    p_diag.add_argument("--sources", default=None, help="Comma-separated preset keys; default all presets")
    p_diag.set_defaults(func=cmd_calendar_diagnostics)

    p_pre = sub.add_parser("pre", help="Render a pre-release playbook")
    p_pre.add_argument("--country", required=True)
    p_pre.add_argument("--event", required=True)
    p_pre.set_defaults(func=cmd_pre)

    p_assess = sub.add_parser("assess-release", help="Render a detailed actual news announcement assessment")
    _add_release_args(p_assess)
    p_assess.set_defaults(func=cmd_assess_release)

    p_cluster = sub.add_parser("assess-cluster", help="Assess several releases published together")
    p_cluster.add_argument("--country", required=True)
    p_cluster.add_argument("--events", required=True, help="Comma-separated event codes, e.g. CPI,CORE_CPI")
    p_cluster.add_argument("--actuals", required=True, help="Comma-separated actual values")
    p_cluster.add_argument("--forecasts", default=None, help="Comma-separated forecast values; use blank/none for missing")
    p_cluster.add_argument("--previous", default=None, help="Comma-separated previous values; use blank/none for missing")
    p_cluster.add_argument("--json", action="store_true")
    p_cluster.set_defaults(func=cmd_assess_cluster)

    p_score = sub.add_parser("score", help="Score a macro release")
    _add_release_args(p_score)
    p_score.set_defaults(func=cmd_score)

    p_report = sub.add_parser("report", help="Render a post-release report")
    _add_release_args(p_report)
    p_report.set_defaults(func=cmd_report)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
