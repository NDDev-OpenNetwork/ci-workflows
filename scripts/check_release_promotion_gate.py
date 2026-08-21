#!/usr/bin/env python3
"""Executable regression checks for the reusable release promotion gate."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
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
RELEASE_WORKFLOW = WORKFLOWS_DIR / "release.yml"
RENDERER = WORKFLOW.parents[2] / "scripts" / "render-public-promotion-record.sh"
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
    index = {"public-ci": 1, "public-contract": 2, "public-security": 3}[role]
    payload = _evidence_payload(role)
    canonical = json.dumps(
        payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    return {
        "digest": "sha256:" + hashlib.sha256(canonical.encode()).hexdigest(),
        "observed_at": payload["completed_at"] if role == "public-contract" else payload["updated_at"],
        "public_commit": PUBLIC_SHA,
        "result": "success",
        "role": role,
        "source": (
            f"https://github.com/NDDev-OpenNetwork/nddev-example-app/actions/runs/{index}/job/22"
            if role == "public-contract"
            else f"https://github.com/NDDev-OpenNetwork/nddev-example-app/actions/runs/{index}"
        ),
    }


def _evidence_payload(role: str) -> dict[str, Any]:
    index = {"public-ci": 1, "public-contract": 2, "public-security": 3}[role]
    source = (
        f"https://github.com/{PUBLIC_REPOSITORY}/actions/runs/{index}/job/22"
        if role == "public-contract"
        else f"https://github.com/{PUBLIC_REPOSITORY}/actions/runs/{index}"
    )
    if role == "public-contract":
        return {
            "completed_at": _timestamp(NOW - dt.timedelta(hours=1)),
            "conclusion": "success",
            "head_sha": PUBLIC_SHA,
            "html_url": source,
            "id": 22,
            "name": "static validators",
            "run_id": 2,
            "started_at": _timestamp(NOW - dt.timedelta(hours=1, minutes=2)),
            "status": "completed",
        }
    return {
        "conclusion": "success",
        "created_at": _timestamp(NOW - dt.timedelta(hours=1, minutes=3)),
        "event": "push",
        "head_sha": PUBLIC_SHA,
        "html_url": source,
        "id": index,
        "name": "ci" if role == "public-ci" else "codeql",
        "run_attempt": 1,
        "status": "completed",
        "updated_at": _timestamp(NOW - dt.timedelta(hours=1)),
        "workflow_id": 100 + index,
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
        evidence_dir = root / "evidence"
        evidence_dir.mkdir()
        ref_path.write_text(json.dumps(ref), encoding="utf-8")
        tag_path.write_text(json.dumps(tag), encoding="utf-8")
        for role in ("public-ci", "public-contract", "public-security"):
            (evidence_dir / f"{role}.json").write_text(
                json.dumps(_evidence_payload(role)), encoding="utf-8"
            )
        env = clean_environment({
                "PROMOTION_NOW": _timestamp(NOW),
                "PROMOTION_EVIDENCE_DIR": str(evidence_dir),
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


def _check_renderer() -> list[str]:
    with tempfile.TemporaryDirectory(prefix="release-promotion-renderer-") as raw:
        root = Path(raw)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        payloads = {
            f"repos/{PUBLIC_REPOSITORY}/actions/runs/1": _evidence_payload("public-ci"),
            f"repos/{PUBLIC_REPOSITORY}/actions/jobs/22": _evidence_payload("public-contract"),
            f"repos/{PUBLIC_REPOSITORY}/actions/runs/3": _evidence_payload("public-security"),
        }
        gh = bin_dir / "gh"
        gh.write_text(
            f"#!{sys.executable}\n"
            "import json, sys\n"
            f"payloads = {payloads!r}\n"
            "if len(sys.argv) != 3 or sys.argv[1] != 'api' or sys.argv[2] not in payloads:\n"
            "    raise SystemExit(2)\n"
            "print(json.dumps(payloads[sys.argv[2]]))\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)
        record = _record()
        command = [
            str(RENDERER), "1.2.3", PUBLIC_REPOSITORY, PUBLIC_SHA,
            record["generated_at"], record["expires_at"],
            record["evidence"][0]["source"], record["evidence"][1]["source"],
            record["evidence"][2]["source"],
        ]
        env = clean_environment({
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "TMPDIR": str(root),
        })
        result = subprocess.run(
            command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, check=False,
        )
        if result.returncode != 0:
            return [f"public promotion renderer failed: {result.stderr.strip()}"]
        try:
            rendered = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            return [f"public promotion renderer returned invalid JSON: {exc}"]
        if rendered != record:
            return ["public promotion renderer did not derive the expected API-bound record"]
    return []


def check() -> list[str]:
    problems: list[str] = _check_renderer()
    try:
        workflow = load_yaml(WORKFLOW)
        release_workflow = load_yaml(RELEASE_WORKFLOW)
        program = _program(workflow)
    except (OSError, ValueError, TypeError) as exc:
        return [str(exc)]

    called_permissions = workflow.get("jobs", {}).get("promotion", {}).get("permissions", {})
    caller_permissions = release_workflow.get("jobs", {}).get("promotion", {}).get("permissions", {})
    levels = {None: 0, "none": 0, "read": 1, "write": 2}
    if not isinstance(called_permissions, dict) or not isinstance(caller_permissions, dict):
        problems.append("promotion caller and reusable job permissions must be mappings")
    else:
        for scope, required in called_permissions.items():
            if levels.get(caller_permissions.get(scope), -1) < levels.get(required, -1):
                problems.append(
                    f"release promotion caller does not grant reusable scope {scope}: {required}"
                )

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
            "fabricated evidence digest",
            _mutate(
                _record(),
                lambda r: r["evidence"][0].__setitem__("digest", "sha256:" + "9" * 64),
            ),
            True,
        ),
        (
            "fabricated evidence timestamp",
            _mutate(
                _record(),
                lambda r: r["evidence"][0].__setitem__(
                    "observed_at", _timestamp(NOW - dt.timedelta(hours=2))
                ),
            ),
            True,
        ),
        (
            "duplicate evidence source",
            _mutate(
                _record(),
                lambda r: r["evidence"][1].__setitem__("source", r["evidence"][0]["source"]),
            ),
            True,
        ),
        (
            "cross-repository evidence source",
            _mutate(
                _record(),
                lambda r: r["evidence"][0].__setitem__("source", "https://github.com/other/repo/actions/runs/1"),
            ),
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
