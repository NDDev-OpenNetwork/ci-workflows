#!/usr/bin/env python3
"""Every third-party `uses:` must be pinned to a full 40-char commit SHA with a
version comment. Local reusable calls (`./.github/...`) are exempt.
"""
from __future__ import annotations

import re
import sys

from ci_workflows_tools._workflow_yaml import workflow_files

# `uses: owner/repo[/path]@<40-hex>  # vX.Y.Z`
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<ref>\S+)(?P<rest>.*)$")
SHA_RE = re.compile(r"@[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"@sha256:[0-9a-f]{64}$")
# The comment must say *which release* the SHA is, because that is the only
# human-readable half of the pin: a reviewer diffing a Dependabot bump reads the
# comment, and a bare `#` or `# bumped` both satisfied the old presence-only
# test. A semantic release version or an ISO date for an untagged upstream
# identifies stable inputs. An unreleased development input must instead name
# its exact commit, equal to the immutable ref, rather than inventing a release.
PIN_COMMENT_RE = re.compile(r"#\s*(v?\d+\.\d+(?:\.\d+)?[\w.+-]*|\d{4}-\d{2}-\d{2})\b")


DEVELOPMENT_COMMENT_RE = re.compile(r"^\s*#\s*commit:([0-9a-f]{40})(?:\s|$)")


def supported_pin_comment(ref: str, comment: str) -> bool:
    if re.match(r"^\s*#\s*commit:", comment):
        match = DEVELOPMENT_COMMENT_RE.search(comment)
        return match is not None and match.group(1) == ref.rsplit("@", 1)[-1]
    return PIN_COMMENT_RE.search(comment) is not None


def check() -> list[str]:
    problems: list[str] = _selftest()
    for path in workflow_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = USES_RE.match(line)
            if not m:
                continue
            ref = m.group("ref").strip().strip("'\"")
            rest = m.group("rest")
            where = f"{path.name}:{lineno}"
            if ref.startswith("./"):
                continue  # local reusable workflow
            if ref.startswith("docker://"):
                if not DIGEST_RE.search(ref):
                    problems.append(f"{where}: docker image not digest-pinned: {ref}")
                continue
            if "@" not in ref:
                problems.append(f"{where}: action not pinned (no @ref): {ref}")
                continue
            if not SHA_RE.search(ref):
                problems.append(f"{where}: action not pinned to a 40-char SHA: {ref}")
                continue
            if "#" not in rest:
                problems.append(f"{where}: SHA pin missing a `# vX.Y.Z` version comment: {ref}")
            elif not supported_pin_comment(ref, rest):
                problems.append(
                    f"{where}: SHA pin comment must name the release "
                    f"(`# vX.Y.Z`, or `# YYYY-MM-DD` for an upstream that tags no "
                    f"releases; or # commit:<same full SHA>), got {rest.strip()!r}: {ref}"
                )
    return problems


def _selftest() -> list[str]:
    """Accept the real forms in this tree; reject a comment that says nothing."""
    problems: list[str] = []
    for good in ("  # v7.0.1", "  # v2.20.0", "  # 2024-09-19", "  # v0.36.0",
                 "  # v12.3114", "  # v4.1.1  (attest storage record)"):
        if PIN_COMMENT_RE.search(good) is None:
            problems.append(f"check_pinned_actions self-test: rejected {good.strip()!r}")
    for bad in ("  #", "  # bumped", "  # see PR", "  # latest", "  #  "):
        if PIN_COMMENT_RE.search(bad) is not None:
            problems.append(f"check_pinned_actions self-test: accepted {bad.strip()!r}")
    development_sha = "a" * 40
    development_ref = "example/action@" + development_sha
    if not supported_pin_comment(development_ref, " # commit:" + development_sha):
        problems.append("check_pinned_actions self-test: rejected exact development commit")
    for comment in (
        " # commit:" + "b" * 40,
        " # commit:" + "a" * 7,
        " # commit:" + "a" * 41,
        " # commit:wrong # v1.0.0",
    ):
        if supported_pin_comment(development_ref, comment):
            problems.append("check_pinned_actions self-test: accepted mismatched development identity")
    return problems


def main() -> int:
    problems = check()
    if problems:
        print("check_pinned_actions: FAIL", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("check_pinned_actions: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
