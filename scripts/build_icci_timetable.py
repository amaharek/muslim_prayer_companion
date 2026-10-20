#!/usr/bin/env python3
"""
Build or verify the bundled ICCI timetable (data/icci_timetable.json).

The Islamic Cultural Centre of Ireland used to publish its perpetual timetable
as JSON at https://islamireland.ie/api/timetable/. The endpoint now serves the
website's HTML, so the integration ships the last published copy, taken from
the Wayback Machine snapshot of 2 August 2022 (identical to the 2018 and 2019
snapshots). Both checksums below were verified against that snapshot.

    python -I scripts/build_icci_timetable.py --check
        Verify the committed file: checksum, 366 days, source block, exact layout.
    python -I scripts/build_icci_timetable.py --download
        Download the snapshot, verify it and rewrite the committed file.
    python -I scripts/build_icci_timetable.py --input downloaded.json [--output PATH]
        Build the file from an already downloaded copy.

Stdlib only, so it runs with ``python -I`` (no site-packages, no cwd imports).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = (
    ROOT / "custom_components" / "muslim_prayer_companion" / "data" / "icci_timetable.json"
)

SNAPSHOT_URL = (
    "https://web.archive.org/web/20220802110619id_/https://islamireland.ie/api/timetable/"
)
RAW_SHA256 = "9aff0c8a8965c69555bc6fddd68f7206412bc3d1b069f3c99c1c5518a3abed35"
CANONICAL_SHA256 = "7309f36e1d557b84e6ba3a0697ab4f340fd23c4b8cc1843ab32c9b7feea87af6"
EXPECTED_DAYS = 366
PRAYERS_PER_DAY = 6

SOURCE = {
    "url": "https://islamireland.ie/api/timetable/",
    "snapshot_url": SNAPSHOT_URL,
    "snapshot_date": "2022-08-02",
    "updated": 1528119190,
    "note": (
        "Perpetual timetable of the Islamic Cultural Centre of Ireland (ICCI). "
        "Keyed by month then day, with no year (29 Feb included). Each day lists "
        "[hour, minute] for fajr, shurooq (sunrise), dhuhr, asr, maghrib and isha "
        "in local Irish clock time (IST in summer, GMT in winter). The table "
        "changes clocks on 1 April and 1 November, not on the actual DST dates."
    ),
}

Timetable = dict[str, dict[str, list[list[int]]]]


def canonical_sha256(timetable: Timetable) -> str:
    """Return the SHA-256 of the timetable in canonical JSON form."""
    canonical = json.dumps(timetable, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def render(timetable: Timetable) -> str:
    """Render the data file: 2-space indent, one day per line, months in order."""
    lines = ["{", '  "_source": {']
    source_items = list(SOURCE.items())
    for index, (key, value) in enumerate(source_items):
        comma = "," if index < len(source_items) - 1 else ""
        lines.append(f"    {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}{comma}")
    lines.extend(["  },", '  "timetable": {'])
    months = sorted(timetable, key=int)
    for month_index, month in enumerate(months):
        lines.append(f'    "{month}": {{')
        days = sorted(timetable[month], key=int)
        for day_index, day in enumerate(days):
            pairs = ", ".join(f"[{hour}, {minute}]" for hour, minute in timetable[month][day])
            comma = "," if day_index < len(days) - 1 else ""
            lines.append(f'      "{day}": [{pairs}]{comma}')
        lines.append("    }" + ("," if month_index < len(months) - 1 else ""))
    lines.extend(["  }", "}"])
    return "\n".join(lines) + "\n"


def validate_timetable(timetable: Any) -> list[str]:
    """Return the problems found in a timetable object (empty when it is fine)."""
    problems: list[str] = []
    if not isinstance(timetable, dict):
        return ["timetable is not an object"]
    days = sum(len(month) for month in timetable.values() if isinstance(month, dict))
    if days != EXPECTED_DAYS:
        problems.append(f"expected {EXPECTED_DAYS} days, found {days}")
    for month, month_days in timetable.items():
        if not isinstance(month_days, dict):
            problems.append(f"month {month} is not an object")
            continue
        for day, prayers in month_days.items():
            ok = (
                isinstance(prayers, list)
                and len(prayers) == PRAYERS_PER_DAY
                and all(
                    isinstance(pair, list)
                    and len(pair) == 2
                    and all(isinstance(v, int) for v in pair)
                    and 0 <= pair[0] < 24
                    and 0 <= pair[1] < 60
                    for pair in prayers
                )
            )
            if not ok:
                problems.append(f"invalid prayer times for {day}/{month}")
    digest = canonical_sha256(timetable)
    if digest != CANONICAL_SHA256:
        problems.append(f"canonical SHA-256 mismatch: {digest}")
    return problems


def timetable_from_raw(raw: bytes) -> Timetable:
    """Verify a downloaded snapshot and return its timetable."""
    raw_digest = hashlib.sha256(raw).hexdigest()
    if raw_digest != RAW_SHA256:
        msg = f"raw SHA-256 mismatch: {raw_digest} (expected {RAW_SHA256})"
        raise SystemExit(msg)
    data = json.loads(raw)
    timetable = data["timetable"]
    problems = validate_timetable(timetable)
    if problems:
        raise SystemExit("snapshot is not usable:\n  " + "\n  ".join(problems))
    return timetable


def download() -> bytes:
    """Download the Wayback Machine snapshot."""
    request = urllib.request.Request(
        SNAPSHOT_URL, headers={"User-Agent": "muslim_prayer_companion build script"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def build(raw: bytes, output: Path) -> None:
    """Write the data file from a verified snapshot."""
    timetable = timetable_from_raw(raw)
    text = render(timetable)
    written = json.loads(text)
    if written["timetable"] != timetable or written["_source"] != SOURCE:
        msg = "round-trip mismatch after rendering"
        raise SystemExit(msg)
    output.write_text(text, encoding="utf-8")
    print(f"raw sha256 ok, canonical sha256 ok, wrote {output} ({len(text)} bytes)")


def check(path: Path) -> list[str]:
    """Return the problems with the committed data file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as err:
        return [f"cannot read {path}: {err}"]
    try:
        data = json.loads(text)
    except ValueError as err:
        return [f"{path} is not valid JSON: {err}"]
    problems: list[str] = []
    if data.get("_source") != SOURCE:
        problems.append("_source block differs from the expected one")
    timetable = data.get("timetable")
    problems.extend(validate_timetable(timetable))
    if not problems and render(timetable) != text:
        problems.append("file layout differs from the generator's output")
    return problems


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="verify the committed data file")
    mode.add_argument("--download", action="store_true", help="download the snapshot and build")
    mode.add_argument("--input", type=Path, help="build from a downloaded snapshot file")
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="data file to write/check"
    )
    args = parser.parse_args(argv)

    if args.check:
        problems = check(args.output)
        if problems:
            print(f"{args.output}:\n  " + "\n  ".join(problems), file=sys.stderr)
            return 1
        print(f"{args.output}: canonical sha256 ok, {EXPECTED_DAYS} days, layout ok")
        return 0

    raw = download() if args.download else args.input.read_bytes()
    build(raw, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
