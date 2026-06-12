from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from .calendar_sources import MultiSourceCalendar, SourceAttempt, build_preset_sources
from .storage import PROCESSED_DIR, ensure_data_dirs


def run_calendar_diagnostics(target_date: date, source_keys: list[str] | None = None) -> tuple[Path, list[SourceAttempt], int]:
    ensure_data_dirs()
    multi = MultiSourceCalendar(build_preset_sources(source_keys))
    result = multi.fetch_calendar_result(target_date)
    path = PROCESSED_DIR / f"calendar_diagnostics_{target_date.isoformat()}.md"
    path.write_text(render_diagnostics_markdown(target_date, result.attempts, len(result.events)), encoding="utf-8")
    return path, result.attempts, len(result.events)


def render_diagnostics_markdown(target_date: date, attempts: list[SourceAttempt], deduped_events: int) -> str:
    lines = [
        f"# Calendar Source Diagnostics — {target_date.isoformat()}",
        "",
        f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z",
        f"Deduped events: {deduped_events}",
        "",
        "| Source | Status | Events | Error |",
        "|---|---:|---:|---|",
    ]
    for attempt in attempts:
        status = "OK" if attempt.ok else "FAIL"
        error = (attempt.error or "").replace("\n", " ").replace("|", "/")
        lines.append(f"| {attempt.source} | {status} | {attempt.events} | {error} |")
    lines += [
        "",
        "## Interpretation",
        "",
        "A source returning zero events is not automatically useless. It may have no G10 events for the requested date, require a custom adapter, require JavaScript rendering, require login/session cookies, or expose data through a separate export/API endpoint.",
        "",
        "The goal is not to trust every source. The goal is to identify which sources produce repeatable, normalized, verifiable rows and use weaker sources only as fallbacks.",
    ]
    return "\n".join(lines) + "\n"
