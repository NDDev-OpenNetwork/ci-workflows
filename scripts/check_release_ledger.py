#!/usr/bin/env python3
"""`CHANGELOG.md` is a release ledger, so every heading must be a real release.

`release.yml` checks the forward direction — the tag being published equals
`VERSION` and has exactly one matching heading — and nothing ever checked the
reverse. That let `## [0.11.0] - 2026-07-20` sit in the ledger for a month
describing a release that was never tagged and therefore never existed, between
`0.10.0` and `0.11.1` which both did. Two more headings carried dates a day
before their own tag, one of them putting a patch release before the minor it
patches.

The split follows the repository's tier rule. Heading grammar, ordering, date
monotonicity and agreement with `VERSION` are properties of the tree in hand,
so they block in `core`. Whether a tag exists is a property of the refs, not of
the change, so tag reconciliation is advisory and runs in the scheduled sweep —
the same reason a third party's pricing page cannot block an unrelated bugfix.
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from ci_workflows_tools.check_python_execution_contract import clean_environment

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
VERSION_FILE = REPO_ROOT / "VERSION"

UNRELEASED = "## [Unreleased]"
RELEASE_HEADING = re.compile(
    r"^## \[((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))\]"
    r"(?: - (\d{4}-\d{2}-\d{2}))?$"
)
ANY_VERSION_HEADING = re.compile(r"^## \[(?!Unreleased\])(.*?)\]")

# A released heading with no tag. Recording it here keeps the advisory sweep
# actionable instead of permanently red, and puts the anomaly somewhere a
# reader will actually meet it. Creating the missing tag needs tag-write
# authority, which is deliberately outside what this repository's validators do.
KNOWN_UNTAGGED: dict[str, str] = {}

# Signed tags whose immutable target failed release preflight and therefore has
# no GitHub Release. They are retained as failure evidence, but they are not
# release headings and consumers must never treat them as published versions.
KNOWN_UNRELEASED_TAGS: dict[str, str] = {
    "0.1.4": "tag target still declared VERSION 0.1.3; preflight rejected run 32620039075",
    "0.1.5": "historical 0.1.4 tag lacked a release heading; preflight rejected run 32748217729",
}


def _headings() -> tuple[list[tuple[int, str, str | None]], list[str]]:
    """Every release heading as (line number, version, date), plus problems."""
    problems: list[str] = []
    try:
        lines = CHANGELOG.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"cannot read CHANGELOG.md: {exc}"]
    headings: list[tuple[int, str, str | None]] = []
    for number, line in enumerate(lines, 1):
        if not line.startswith("## ["):
            continue
        if line == UNRELEASED:
            continue
        match = RELEASE_HEADING.fullmatch(line)
        if match is None:
            loose = ANY_VERSION_HEADING.match(line)
            label = loose.group(1) if loose else line
            problems.append(
                f"CHANGELOG.md:{number}: {label!r} is not a `## [X.Y.Z] - YYYY-MM-DD` "
                "release heading"
            )
            continue
        headings.append((number, match.group(1), match.group(2)))
    return headings, problems


def _semver(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def check() -> list[str]:
    """Blocking: the ledger's own structure, and the reconciliation rules.

    The rules live here rather than in the advisory sweep on purpose: whether a
    tag exists is a property of the refs, but whether the code that reconciles
    them is correct is a property of the tree, and the sweep has never run.
    """
    headings, problems = _headings()
    problems += _selftest()

    try:
        text = CHANGELOG.read_text(encoding="utf-8")
    except OSError:
        return problems
    if text.count(f"\n{UNRELEASED}\n") != 1:
        problems.append("CHANGELOG.md must carry exactly one `## [Unreleased]` heading")
    elif headings and text.index(UNRELEASED) > text.index(f"## [{headings[0][1]}]"):
        problems.append("CHANGELOG.md: `## [Unreleased]` must come before every release")

    seen: dict[str, int] = {}
    for number, version, date in headings:
        if version in seen:
            problems.append(
                f"CHANGELOG.md:{number}: duplicate heading for {version} "
                f"(first at line {seen[version]})"
            )
        seen[version] = number
        if date is None:
            problems.append(f"CHANGELOG.md:{number}: {version} has no release date")

    for (_, newer, newer_date), (line, older, older_date) in zip(headings, headings[1:]):
        if _semver(newer) <= _semver(older):
            problems.append(
                f"CHANGELOG.md:{line}: {older} is not below a strictly greater "
                f"version; {newer} precedes it"
            )
        if newer_date and older_date and older_date > newer_date:
            problems.append(
                f"CHANGELOG.md:{line}: {older} is dated {older_date}, after "
                f"{newer} at {newer_date}; releases run newest first"
            )

    try:
        declared = VERSION_FILE.read_bytes().decode("ascii")
    except (OSError, UnicodeError) as exc:
        problems.append(f"cannot read VERSION: {exc}")
        return problems
    if not declared.endswith("\n") or declared.count("\n") != 1:
        problems.append("VERSION must be one LF-terminated line")
    current = declared.strip()
    if current and current not in seen:
        problems.append(
            f"VERSION is {current} but CHANGELOG.md has no `## [{current}]` heading"
        )
    return problems


def _reconcile(
    headings: list[tuple[int, str, str | None]],
    tags: set[str],
    known_untagged: Mapping[str, str],
    tag_date: Callable[[str], str | None],
    known_unreleased_tags: Mapping[str, str] | None = None,
) -> list[str]:
    """Reconcile ledger headings against a tag set. Pure: no git, no filesystem.

    Split out of `check_tags` so the rules can be exercised on explicit inputs.
    Building the interesting cases out of the live repository means the negative
    case asserts whatever happens to be checked out rather than the rule itself,
    which is how a self-test quietly stops testing anything.
    """
    if not tags:
        # Fail closed: a shallow checkout without tags cannot reconcile
        # anything, and silently reporting "all good" is the failure mode this
        # whole file exists to end.
        return ["no SemVer tags are present; fetch tags before reconciling the ledger"]
    problems: list[str] = []
    for _, version, date in headings:
        if version not in tags:
            if known_untagged.get(version) is None:
                problems.append(
                    f"CHANGELOG.md claims {version} was released but no tag exists"
                )
            continue
        tagged = tag_date(version)
        if tagged and date and tagged != date:
            problems.append(
                f"{version} is dated {date} in CHANGELOG.md but its tag is {tagged}"
            )
    known_unreleased_tags = known_unreleased_tags or {}
    for tag in sorted(tags - {version for _, version, _ in headings} - set(known_unreleased_tags)):
        problems.append(f"tag {tag} exists but CHANGELOG.md has no heading for it")
    for version in sorted(known_untagged):
        if version in tags:
            problems.append(
                f"{version} is now tagged; drop it from KNOWN_UNTAGGED in "
                "check_release_ledger.py"
            )
    for version, reason in sorted(known_unreleased_tags.items()):
        if version not in tags:
            problems.append(f"known unreleased tag {version} is absent; remove its exception ({reason})")
        if version in {release for _, release, _ in headings}:
            problems.append(f"known unreleased tag {version} has a release heading; remove its exception")
    return problems


def _selftest() -> list[str]:
    """Every reconciliation rule, on explicit inputs.

    `KNOWN_UNTAGGED` is the escape hatch for a heading whose tag needs authority
    this repository deliberately does not have. An escape hatch nothing tests is
    how a permanent exemption stops being noticed, so the entry that silences a
    finding and the entry that has outlived its reason are both asserted here.
    """
    problems: list[str] = []

    def case(label, headings, tags, known, dates, expected):
        actual = _reconcile(headings, set(tags), known, dates.get)
        if actual != expected:
            problems.append(
                f"reconcile selftest {label!r}: got {actual}, expected {expected}")

    one = [(1, "1.0.0", "2026-01-01")]
    two = [(1, "1.0.0", "2026-01-01"), (2, "2.0.0", "2026-02-02")]

    case("clean", one, {"1.0.0"}, {}, {"1.0.0": "2026-01-01"}, [])
    case("no-tags-fails-closed", one, set(), {}, {},
         ["no SemVer tags are present; fetch tags before reconciling the ledger"])
    case("untagged-heading", two, {"1.0.0"}, {}, {"1.0.0": "2026-01-01"},
         ["CHANGELOG.md claims 2.0.0 was released but no tag exists"])
    case("known-untagged-silences-it", two, {"1.0.0"}, {"2.0.0": "why"},
         {"1.0.0": "2026-01-01"}, [])
    case("known-untagged-now-tagged", one, {"1.0.0"}, {"1.0.0": "why"},
         {"1.0.0": "2026-01-01"},
         ["1.0.0 is now tagged; drop it from KNOWN_UNTAGGED in "
          "check_release_ledger.py"])
    case("tag-without-heading", one, {"1.0.0", "1.1.0"}, {},
         {"1.0.0": "2026-01-01"},
         ["tag 1.1.0 exists but CHANGELOG.md has no heading for it"])
    actual = _reconcile(one, {"1.0.0", "1.1.0"}, {}, {"1.0.0": "2026-01-01"}.get,
                        {"1.1.0": "rejected"})
    if actual:
        problems.append(f"reconcile selftest known-unreleased-tag: got {actual}, expected []")
    case("date-mismatch", one, {"1.0.0"}, {}, {"1.0.0": "2026-01-02"},
         ["1.0.0 is dated 2026-01-01 in CHANGELOG.md but its tag is 2026-01-02"])
    case("unknown-tag-date-tolerated", one, {"1.0.0"}, {}, {}, [])

    for version, reason in KNOWN_UNTAGGED.items():
        if not str(reason).strip():
            problems.append(f"KNOWN_UNTAGGED[{version!r}] carries no reason")
    return problems


def check_tags() -> list[str]:
    """Advisory: every released heading is a tag, and every tag is a heading."""
    headings, problems = _headings()
    listed = subprocess.run(
        ["git", "tag", "--list"],
        cwd=REPO_ROOT, env=clean_environment(), capture_output=True, text=True, check=False,
    )
    if listed.returncode != 0:
        return problems + [f"cannot list git tags: {listed.stderr.strip()}"]
    tags = {
        tag for tag in listed.stdout.split()
        if re.fullmatch(r"\d+\.\d+\.\d+", tag)
    }

    def tag_date(version: str) -> str | None:
        shown = subprocess.run(
            ["git", "log", "-1", "--format=%ad", "--date=short", version],
            cwd=REPO_ROOT, env=clean_environment(), capture_output=True, text=True, check=False,
        )
        return shown.stdout.strip() if shown.returncode == 0 else None

    return problems + _reconcile(
        headings, tags, KNOWN_UNTAGGED, tag_date, KNOWN_UNRELEASED_TAGS
    )


def main() -> int:
    problems = check() + check_tags()
    if problems:
        print("check_release_ledger: FAIL", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("check_release_ledger: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
