from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date

from .catalog import filter_catalog, list_countries
from .models import MacroRelease
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


def cmd_countries(_: argparse.Namespace) -> None:
    for c in list_countries():
        print(f"{c.code:<2}  {c.name:<16} {c.currency:<3}  {c.central_bank}")


def cmd_catalog(args: argparse.Namespace) -> None:
    events = filter_catalog(country_code=args.country, impact=args.impact)
    for e in events:
        channels = ",".join(c.value for c in e.channels)
        print(f"{e.country_code:<2} {e.event_code:<24} {e.impact.value:<6} {channels:<38} {e.name}")


def cmd_pre(args: argparse.Namespace) -> None:
    print(render_pre_release(args.country, args.event))


def cmd_calendar_import(args: argparse.Namespace) -> None:
    target = _parse_date(args.date)
    if args.csv:
        source = ManualCalendarCSVSource(args.csv)
    elif args.url:
        source = GenericHTMLCalendarSource(args.url, source_name=args.source_name or "generic_html")
    else:
        raise SystemExit("calendar-import requires --csv or --url")

    events = source.fetch_calendar(target)
    if args.country:
        events = [e for e in events if e.country_code == args.country.upper()]
    if args.impact:
        events = [e for e in events if e.impact.lower() == args.impact.lower()]

    out_path = save_calendar_events(events, target, label=args.label or source.source_name)
    print(f"Imported {len(events)} events for {target} -> {out_path}")
    for e in events[: args.preview]:
        when = e.scheduled_at.isoformat() if e.scheduled_at else "unscheduled"
        print(f"{when:<25} {e.country_code:<2} {e.event_code:<24} {e.impact:<6} {e.name}")


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

    p_catalog = sub.add_parser("catalog", help="List macro event catalog")
    p_catalog.add_argument("--country", default=None)
    p_catalog.add_argument("--impact", choices=["high", "medium", "low"], default=None)
    p_catalog.set_defaults(func=cmd_catalog)

    p_calendar_view = sub.add_parser("calendar-view", help="View catalog events by country/impact")
    p_calendar_view.add_argument("--date", default=None)
    p_calendar_view.add_argument("--country", default=None)
    p_calendar_view.add_argument("--impact", choices=["high", "medium", "low"], default=None)
    p_calendar_view.set_defaults(func=cmd_calendar_view)

    p_calendar_import = sub.add_parser("calendar-import", help="Import economic calendar events from CSV or generic HTML table URL")
    p_calendar_import.add_argument("--date", default=None, help="Target date YYYY-MM-DD; default today")
    p_calendar_import.add_argument("--csv", default=None, help="Normalized CSV calendar file")
    p_calendar_import.add_argument("--url", default=None, help="Public HTML page containing ordinary calendar tables")
    p_calendar_import.add_argument("--source-name", default=None)
    p_calendar_import.add_argument("--label", default=None, help="Output file label")
    p_calendar_import.add_argument("--country", default=None)
    p_calendar_import.add_argument("--impact", choices=["high", "medium", "low"], default=None)
    p_calendar_import.add_argument("--preview", type=int, default=25)
    p_calendar_import.set_defaults(func=cmd_calendar_import)

    p_pre = sub.add_parser("pre", help="Render a pre-release playbook")
    p_pre.add_argument("--country", required=True)
    p_pre.add_argument("--event", required=True)
    p_pre.set_defaults(func=cmd_pre)

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
