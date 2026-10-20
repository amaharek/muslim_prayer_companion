#!/usr/bin/env python3
"""
Check that every mosque source in data/mosques.json still works.

Each source is fetched and parsed with the integration's own parsers, so this
fails exactly when the integration would fall back to calculated times.

    python scripts/check_mosques.py            # fetch every source (needs network)
    python scripts/check_mosques.py --offline  # registry and bundled data only
    python scripts/check_mosques.py --report mosque-health.md

Run it from a development environment (``pip install -e ".[dev]"``); the
parsers live inside the integration package, which imports Home Assistant.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from custom_components.muslim_prayer_companion.api_providers.dpt import (  # noqa: E402
    parse_dpt_payload,
)
from custom_components.muslim_prayer_companion.api_providers.icci_timetable import (  # noqa: E402
    build_icci_result,
    load_icci_timetable,
)
from custom_components.muslim_prayer_companion.api_providers.mai import (  # noqa: E402
    build_mai_result,
    parse_mai_homepage,
)
from custom_components.muslim_prayer_companion.helpers.registry import (  # noqa: E402
    MOSQUES,
    SOURCE_TYPE_DPT,
    SOURCE_TYPE_ICCI_TIMETABLE,
    SOURCE_TYPE_MAI_HTML,
    Mosque,
)

USER_AGENT = (
    "muslim_prayer_companion health check (+https://github.com/amaharek/muslim_prayer_companion)"
)
TIMEOUT_SECONDS = 20


@dataclass
class Outcome:
    """Result of checking one mosque."""

    mosque: Mosque
    ok: bool
    detail: str


def fetch(url: str) -> str:
    """GET a URL and return the body as text."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def check_mosque(mosque: Mosque, *, offline: bool) -> Outcome:
    """Fetch and parse one mosque's source."""
    tz = ZoneInfo(mosque.timezone)
    today = datetime.now(UTC).astimezone(tz).date()
    source = mosque.source
    try:
        if source.type == SOURCE_TYPE_ICCI_TIMETABLE:
            timetable = load_icci_timetable()
            if timetable is None:
                return Outcome(mosque, ok=False, detail="bundled timetable missing or corrupt")
            result = build_icci_result(timetable, today)
        elif offline:
            return Outcome(mosque, ok=True, detail="skipped (offline)")
        elif source.type == SOURCE_TYPE_DPT:
            text = fetch(source.url or "")
            try:
                payload = json.loads(text)
            except ValueError:
                preview = text.strip()[:60]
                return Outcome(mosque, ok=False, detail=f"not JSON (starts with {preview!r})")
            result = parse_dpt_payload(payload, today, tz, mosque.source_id)
        elif source.type == SOURCE_TYPE_MAI_HTML:
            parsed = parse_mai_homepage(fetch(source.url or ""))
            result = build_mai_result(parsed, today, tz)
        else:
            return Outcome(mosque, ok=False, detail=f"unknown source type {source.type!r}")
        result.today.validate()
    except urllib.error.URLError as err:
        return Outcome(mosque, ok=False, detail=f"network error: {err}")
    except Exception as err:  # noqa: BLE001 - report anything, this is a health check
        return Outcome(mosque, ok=False, detail=f"{type(err).__name__}: {err}")

    maghrib = result.today.maghrib.astimezone(tz).strftime("%H:%M")
    extras = []
    if result.iqamah is not None:
        extras.append("iqamah")
    if result.jumuah:
        extras.append(f"{len(result.jumuah)} jumu'ah")
    if result.tomorrow is not None:
        extras.append("tomorrow")
    detail = f"Maghrib {maghrib}" + (f" ({', '.join(extras)})" if extras else "")
    return Outcome(mosque, ok=True, detail=detail)


def markdown_report(outcomes: list[Outcome], when: datetime) -> str:
    """Return a Markdown table of the outcomes."""
    lines = [
        f"Mosque source check on {when:%Y-%m-%d %H:%M} UTC",
        "",
        "| Mosque | Source | Status | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for outcome in outcomes:
        status = "OK" if outcome.ok else "FAILED"
        url = outcome.mosque.source.url or outcome.mosque.website
        lines.append(
            f"| {outcome.mosque.name} (`{outcome.mosque.key}`) | {outcome.mosque.source.type} ({url}) "
            f"| {status} | {outcome.detail} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Run the check and return the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--offline", action="store_true", help="only check the registry and bundled data"
    )
    parser.add_argument("--report", type=Path, help="write a Markdown report to this file")
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    outcomes = [check_mosque(mosque, offline=args.offline) for mosque in MOSQUES.values()]
    report = markdown_report(outcomes, now)
    print(report)
    if args.report:
        args.report.write_text(report, encoding="utf-8")

    failed = [outcome for outcome in outcomes if not outcome.ok]
    if failed:
        print(f"{len(failed)} of {len(outcomes)} mosque sources failed", file=sys.stderr)
        return 1
    print(f"All {len(outcomes)} mosque sources OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
