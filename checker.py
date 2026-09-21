#!/usr/bin/env python3
"""
Engineering journal completeness checker.

Usage:
    python checker.py ENGINEERING_JOURNAL_EXTRACT.md

Exit codes:
    0 = every entry is complete
    1 = one or more entries are missing required pieces
    2 = input/configuration error
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FIELDS = (
    "Symptom",
    "Root cause",
    "What misled us",
    "The rule",
    "Detect it again",
)

ENTRY_RE = re.compile(r"(?m)^##\s+(\d+)\.\s+(.+?)\s*$")

# Flexible labels explicitly allowed by the journal/brief.
FIELD_PATTERNS = {
    "Symptom": [
        re.compile(r"(?im)^\s*(?:\*\*)?Symptom(?:\*\*)?\s*[.:—-]"),
    ],
    "Root cause": [
        re.compile(r"(?im)^\s*(?:\*\*)?Root cause(?:\*\*)?(?:\s*[—-].*?)?\s*[.:—-]"),
    ],
    "What misled us": [
        re.compile(r"(?im)^\s*(?:\*\*)?What misled us(?:\*\*)?\s*[.:—-]"),
        re.compile(r"(?im)^\s*(?:\*\*)?Why it was hard to see(?:\*\*)?\s*[.:—-]"),
    ],
    "The rule": [
        re.compile(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?The rules?(?:\*\*)?\s*[.:—-]"),
    ],
    "Detect it again": [
        re.compile(r"(?im)^\s*(?:\*\*)?Detect it again(?:\*\*)?\s*[.:—-]"),
    ],
}

# A line that looks like a field/section label.
ANY_LABEL_RE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
    r"(?:Symptom|Root cause(?:\s*[—-].*?)?|What misled us|Why it was hard to see|"
    r"The rules?|Detect it again)"
    r"(?:\*\*)?\s*[.:—-]"
)


@dataclass
class Entry:
    number: int
    title: str
    body: str


def parse_entries(text: str) -> list[Entry]:
    """Return numbered journal entries; ignore the index and other ## headings."""
    matches = list(ENTRY_RE.finditer(text))
    entries: list[Entry] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entries.append(
            Entry(
                number=int(match.group(1)),
                title=match.group(2).strip(),
                body=text[start:end].strip(),
            )
        )
    return entries


def has_substantial_narrative_before_misled(body: str) -> bool:
    """
    Tolerate the journal's narrative-style entries.

    The brief says one entry has almost no headings. If BOTH Symptom and Root cause
    labels are absent, but the entry has a recognized "What misled us"/
    "Why it was hard to see" section, we accept the pre-section narrative as
    carrying those two pieces only when it contains at least two substantial
    paragraphs.

    This is intentionally structural rather than entry-number-specific.
    """
    misled_match = None
    for pattern in FIELD_PATTERNS["What misled us"]:
        candidate = pattern.search(body)
        if candidate and (misled_match is None or candidate.start() < misled_match.start()):
            misled_match = candidate

    if not misled_match:
        return False

    prefix = body[:misled_match.start()].strip()
    # Remove a date/metadata line if present.
    prefix = re.sub(r"(?m)^\s*\*?20\d{2}-\d{2}-\d{2}.*$\n?", "", prefix).strip()

    paragraphs = [
        re.sub(r"\s+", " ", p).strip()
        for p in re.split(r"\n\s*\n", prefix)
        if re.sub(r"\s+", " ", p).strip()
    ]
    substantial = [p for p in paragraphs if len(p.split()) >= 18]
    return len(substantial) >= 2


def present_fields(entry: Entry) -> set[str]:
    body = entry.body
    present = {
        field
        for field, patterns in FIELD_PATTERNS.items()
        if any(pattern.search(body) for pattern in patterns)
    }

    # Narrative-format tolerance. We only invoke it when both labels are absent,
    # so a partly structured entry cannot hide one missing field behind prose.
    if "Symptom" not in present and "Root cause" not in present:
        if has_substantial_narrative_before_misled(body):
            present.update({"Symptom", "Root cause"})

    return present


def check_entries(entries: list[Entry]) -> list[tuple[Entry, list[str]]]:
    results = []
    for entry in entries:
        present = present_fields(entry)
        missing = [field for field in REQUIRED_FIELDS if field not in present]
        results.append((entry, missing))
    return results


def render(results: list[tuple[Entry, list[str]]]) -> str:
    lines = []
    for entry, missing in results:
        if missing:
            lines.append(f"Entry {entry.number}: missing {', '.join(missing)}")
        else:
            lines.append(f"Entry {entry.number}: complete")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check engineering journal entry completeness.")
    parser.add_argument("journal", type=Path, help="Path to the engineering journal Markdown file")
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Print findings but exit 0 even if entries are incomplete (useful for demos).",
    )
    args = parser.parse_args()

    if not args.journal.exists():
        print(f"error: journal not found: {args.journal}", file=sys.stderr)
        return 2

    text = args.journal.read_text(encoding="utf-8")
    entries = parse_entries(text)
    if not entries:
        print("error: no numbered journal entries found", file=sys.stderr)
        return 2

    results = check_entries(entries)
    print(render(results))

    incomplete = any(missing for _, missing in results)
    if incomplete and not args.no_fail:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
