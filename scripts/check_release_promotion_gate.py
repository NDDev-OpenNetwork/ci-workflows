#!/usr/bin/env python3
"""Executable regression checks for the reusable release promotion gate."""

from __future__ import annotations

import copy
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from ci_workflows_tools._workflow_yaml import WORKFLOWS_DIR, load_yaml
from ci_workflows_tools.check_python_execution_contract import clean_environment

WORKFLOW = WORKFLOWS_DIR / "release-promotion-gate.yml"
NOW = dt.datetime(2026, 8, 5, 12, 0, tzinfo=dt.timezone.utc)
PUBLIC_REPOSITORY = "NDDev-OpenNetwork/nddev-example-app"
PUBLIC_SHA = "1" * 40
TAG_SHA = "3" * 40


def _program(workflow: dict[str, Any]) -> str:
    steps = workflow.get("jobs", {}).get("promotion", {}).get("steps", [])
    matches = [
        step
        for step in steps
        if isinstance(step, dict) and step.get("name") == "Verify signed promotion record"
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("run"), str):
        raise ValueError("promotion verification step is missing or duplicated")
    lines = matches[0]["run"].splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == "python3 -I <<'PY'"]
    if len(starts) != 1:
        raise ValueError("promotion verification must contain one isolated Python heredoc")
    start = starts[0] + 1
    try:
        end = next(index for index in range(start, len(lines)) if lines[index] == "PY")
    except StopIteration as exc:
        raise ValueError("promotion verification heredoc is not terminated") from exc
    return "\n".join(lines[start:end]) + "\n"


def _timestamp(value: dt.datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _evidence(role: str) -> dict[str, Any]:
    return {
        "digest": "sha256:" + "4" * 64,
        "observed_at": _timestamp(NOW - dt.timedelta(hours=1)),
        "public_commit": PUBLIC_SHA,
        "result": "success",
        "role": role,
        "source": "https://github.com/NDDev-OpenNetwork/nddev-example-app/actions/runs/1",
    }


def _record() -> dict[str, Any]:
    roles = ("public-ci", "public-contract", "public-security")
    return {
        "evidence": [_evidence(role) for role in roles],
        "expires_at": _timestamp(NOW + dt.timedelta(hours=24)),
        "generated_at": _timestamp(NOW - dt.timedelta(minutes=30)),
        "public_commit": PUBLIC_SHA,
        "public_repository": PUBLIC_REPOSITORY,
        "schema": "nddev-public-release-promotion/v2",
        "version": "1.2.3",
    }


def _payload(record: dict[str, Any], *, verified: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    canonical = json.dumps(record, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    signed_payload = (
        f"object {PUBLIC_SHA}\n"
        "type commit\n"
        "tag 1.2.3\n"
        "tagger Release Operator <release@example.invalid> 1785929400 +0000\n\n"
        f"{canonical}\n"
    )
    ref = {
        "node_id": "REF_fixture",
        "object": {
            "sha": TAG_SHA,
            "type": "tag",
            "url": f"https://api.github.invalid/git/tags/{TAG_SHA}",
        },
        "ref": "refs/tags/1.2.3",
        "url": "https://api.github.invalid/git/ref/tags/1.2.3",
    }
    tag = {
        "message": canonical + "\n-----BEGIN SSH SIGNATURE-----\nfixture\n-----END SSH SIGNATURE-----\n",
        "node_id": "TAG_fixture",
        "object": {
            "sha": PUBLIC_SHA,
            "type": "commit",
            "url": f"https://api.github.invalid/git/commits/{PUBLIC_SHA}",
        },
        "sha": TAG_SHA,
        "tag": "1.2.3",
        "tagger": {
            "date": _timestamp(NOW - dt.timedelta(minutes=30)),
            "email": "release@example.invalid",
            "name": "Release Operator",
        },
        "url": f"https://api.github.invalid/git/tags/{TAG_SHA}",
        "verification": {
            "payload": signed_payload,
            "reason": "valid" if verified else "unsigned",
            "signature": "fixture",
            "verified": verified,
            "verified_at": _timestamp(NOW - dt.timedelta(minutes=30)),
        },
    }
    return ref, tag


def _run(program: str, record: dict[str, Any], *, verified: bool = True) -> subprocess.CompletedProcess[str]:
    ref, tag = _payload(record, verified=verified)
    with tempfile.TemporaryDirectory(prefix="release-promotion-test-") as raw:
        root = Path(raw)
        ref_path = root / "ref.json"
        tag_path = root / "tag.json"
        ref_path.write_text(json.dumps(ref), encoding="utf-8")
        tag_path.write_text(json.dumps(tag), encoding="utf-8")
        env = clean_environment({
                "PROMOTION_NOW": _timestamp(NOW),
                "PROMOTION_REF_JSON": str(ref_path),
                "PROMOTION_TAG_JSON": str(tag_path),
                "PUBLIC_REPOSITORY": PUBLIC_REPOSITORY,
                "RELEASE_VERSION": "1.2.3",
        })
        return subprocess.run(
            [sys.executable, "-I", "-"],
            input=program,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )


def _mutate(record: dict[str, Any], mutation: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    changed = copy.deepcopy(record)
    mutation(changed)
    return changed


def check() -> list[str]:
    problems: list[str] = []
    try:
        workflow = load_yaml(WORKFLOW)
        program = _program(workflow)
    except (OSError, ValueError, TypeError) as exc:
        return [str(exc)]

    positive = _run(program, _record())
    if positive.returncode != 0:
        problems.append(f"valid promotion record failed: {positive.stderr.strip()}")

    cases: list[tuple[str, dict[str, Any], bool]] = [
        ("unsigned tag", _record(), False),
        (
            "wrong public sha",
            _mutate(_record(), lambda r: r.__setitem__("public_commit", "6" * 40)),
            True,
        ),
        (
            "wrong repository",
            _mutate(_record(), lambda r: r.__setitem__("public_repository", "other/repo")),
            True,
        ),
        (
            "wrong version",
            _mutate(_record(), lambda r: r.__setitem__("version", "1.2.4")),
            True,
        ),
        (
            "expired record",
            _mutate(_record(), lambda r: r.__setitem__("expires_at", _timestamp(NOW))),
            True,
        ),
        (
            "excessive validity",
            _mutate(
                _record(),
                lambda r: r.__setitem__("expires_at", _timestamp(NOW + dt.timedelta(hours=169))),
            ),
            True,
        ),
        (
            "missing evidence role",
            _mutate(_record(), lambda r: r["evidence"].pop()),
            True,
        ),
        (
            "failed evidence",
            _mutate(_record(), lambda r: r["evidence"][0].__setitem__("result", "failure")),
            True,
        ),
        (
            "wrong evidence public sha",
            _mutate(_record(), lambda r: r["evidence"][0].__setitem__("public_commit", "8" * 40)),
            True,
        ),
        (
            "stale evidence",
            _mutate(
                _record(),
                lambda r: r["evidence"][0].__setitem__(
                    "observed_at", _timestamp(NOW - dt.timedelta(hours=169))
                ),
            ),
            True,
        ),
    ]
    for label, record, verified in cases:
        result = _run(program, record, verified=verified)
        if result.returncode == 0:
            problems.append(f"negative fixture unexpectedly passed: {label}")

    return problems


def main() -> int:
    problems = check()
    if problems:
        print("check_release_promotion_gate: FAIL", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("check_release_promotion_gate: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
