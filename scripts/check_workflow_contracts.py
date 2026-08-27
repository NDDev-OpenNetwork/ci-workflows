#!/usr/bin/env python3
"""Reusable-workflow contract: every workflow except the self workflows
(`ci.yml`, `release.yml`) must be reusable (`on: workflow_call`). The self
workflows must NOT be reusable, and `ci.yml` must expose the `ci-gate` job that
branch protection requires as a status check. Caller-provided command runners
must also fail on the first failing command instead of returning the status of
only the final command. The Go pack's history-depth input remains a typed,
backward-compatible pass-through to checkout.
The private-free workflows used on persistent self-hosted fleets must also
isolate ambient global Git configuration before checkout so runner-owned
Authorization headers cannot combine with actions/checkout's scoped token.
"""
from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

from ci_workflows_tools._runners import is_standard_hosted, resolve_runner_labels
from ci_workflows_tools._workflow_yaml import SELF_WORKFLOWS, get_on, is_reusable, load_yaml, workflow_files


def check() -> list[str]:
    problems: list[str] = []
    for path in workflow_files():
        doc = load_yaml(path)
        reusable = is_reusable(doc)
        if path.name in SELF_WORKFLOWS:
            if reusable:
                problems.append(f"{path.name}: self workflow must not be `on: workflow_call`")
        elif not reusable:
            problems.append(f"{path.name}: reusable workflow missing `on: workflow_call`")

    isolated_checkout_workflows = {
        "actionlint.yml",
        "cross-platform-smoke.yml",
        "private-static.yml",
        "public-codeql.yml",
        "secret-scan.yml",
        "zizmor-no-sarif.yml",
    }
    expected_isolation = """set -euo pipefail
umask 077
isolated_config="$RUNNER_TEMP/nddev-ci-global.gitconfig"
: > "$isolated_config"
printf 'GIT_CONFIG_GLOBAL=%s\\n' "$isolated_config" >> "$GITHUB_ENV"
"""
    workflow_root = workflow_files()[0].parent

    rust_supply_chain = load_yaml(workflow_root / "rust-supply-chain.yml")
    rust_call = get_on(rust_supply_chain).get("workflow_call", {})
    rust_inputs = rust_call.get("inputs", {}) if isinstance(rust_call, dict) else {}
    deny_runner = rust_inputs.get("deny_runner", {}) if isinstance(rust_inputs, dict) else {}
    rust_jobs = rust_supply_chain.get("jobs", {}) or {}
    if (
        not isinstance(deny_runner, dict)
        or deny_runner.get("type") != "string"
        or deny_runner.get("default") != ""
        or (rust_jobs.get("deny", {}) or {}).get("runs-on")
        != "${{ inputs.deny_runner || inputs.runner }}"
        or (rust_jobs.get("audit", {}) or {}).get("runs-on") != "${{ inputs.runner }}"
        or (rust_jobs.get("machete", {}) or {}).get("runs-on") != "${{ inputs.runner }}"
    ):
        problems.append(
            "rust-supply-chain.yml: Docker cargo-deny must expose an optional "
            "deny_runner while audit and machete retain the ordinary runner"
        )

    convergence = load_yaml(workflow_root / "dependabot-catalog-convergence.yml")
    convergence_job = (convergence.get("jobs", {}) or {}).get("synchronize", {})
    convergence_permissions = convergence_job.get("permissions", {})
    if not isinstance(convergence_permissions, dict) or (
        convergence_permissions.get("actions") != "write"
        or convergence_permissions.get("contents") != "write"
        or convergence_permissions.get("pull-requests") != "write"
    ):
        problems.append(
            "dependabot-catalog-convergence.yml: synchronize must retain only "
            "actions, contents, and pull-requests write permissions"
        )
    convergence_steps = convergence_job.get("steps", []) or []
    approval_step = next(
        (
            step
            for step in convergence_steps
            if isinstance(step, dict)
            and step.get("name") == "Approve exact candidate workflow runs"
        ),
        {},
    )
    approval_env = approval_step.get("env", {})
    approval_run = approval_step.get("run", "")
    if not isinstance(approval_env, dict) or approval_env.get("CANDIDATE_SHA") != (
        "${{ steps.commit.outputs.candidate_sha }}"
    ):
        problems.append(
            "dependabot-catalog-convergence.yml: run approval must bind to the "
            "candidate SHA emitted by the commit step"
        )
    required_approval_guards = (
        "event=pull_request&head_sha=${CANDIDATE_SHA}",
        'select(.status == "action_required")',
        "/actions/runs/${run_id}/approve",
    )
    if not isinstance(approval_run, str) or any(
        guard not in approval_run for guard in required_approval_guards
    ):
        problems.append(
            "dependabot-catalog-convergence.yml: approval must select only "
            "action-required pull-request runs for the exact candidate SHA"
        )

    codeql = load_yaml(workflow_root / "public-codeql.yml")
    codeql_on = get_on(codeql)
    codeql_call = codeql_on.get("workflow_call", {}) if isinstance(codeql_on, dict) else {}
    codeql_inputs = codeql_call.get("inputs", {}) if isinstance(codeql_call, dict) else {}
    dependabot_runner = codeql_inputs.get("dependabot_runner", {}) if isinstance(codeql_inputs, dict) else {}
    if not isinstance(dependabot_runner, dict) or dependabot_runner.get("type") != "string" or dependabot_runner.get("default") != "ubuntu-latest":
        problems.append(
            "public-codeql.yml: dependabot_runner must remain a string with the "
            "public-safe ubuntu-latest default"
        )
    codeql_job = (codeql.get("jobs", {}) or {}).get("codeql", {})
    expected_codeql_runner = "${{ github.event_name == 'pull_request' && github.event.pull_request.user.login == 'dependabot[bot]' && inputs.dependabot_runner || inputs.runner }}"
    if codeql_job.get("runs-on") != expected_codeql_runner:
        problems.append(
            "public-codeql.yml: runner selection must explicitly isolate "
            "Dependabot-authored pull requests"
        )
    boundary_steps = [
        step for step in (codeql_job.get("steps", []) or [])
        if isinstance(step, dict) and step.get("name") == "Record CodeQL trust boundary"
    ]
    if len(boundary_steps) != 1 or (boundary_steps[0].get("env") or {}).get("SELECTED_RUNNER") != expected_codeql_runner:
        problems.append(
            "public-codeql.yml: selected Dependabot/ordinary runner boundary must "
            "be emitted as job evidence"
        )
    if "pull_request_target" in (workflow_root / "public-codeql.yml").read_text(encoding="utf-8"):
        problems.append("public-codeql.yml: Dependabot analysis must never use pull_request_target")

    # The consolidated scanner requires four output paths before it can create
    # empty fail-safe evidence. Changing the shared script without wiring every
    # caller broke the first public-product consumer ring at shell expansion,
    # before any scanner ran. Hold the paid/private bundle to the same complete
    # evidence contract as the free bundle.
    nddev_bundle = load_yaml(workflow_root / "nddev-security-bundle.yml")
    bundle_steps = (nddev_bundle.get("jobs", {}).get("security-bundle", {}).get("steps", []) or [])
    scan_steps = [step for step in bundle_steps if isinstance(step, dict) and step.get("name") == "Run consolidated security gates"]
    required_evidence_env = {
        "ZIZMOR_SARIF_PATH",
        "OSV_SARIF_PATH",
        "GITLEAKS_SARIF_PATH",
        "ACTIONLINT_LOG_PATH",
    }
    if len(scan_steps) != 1 or not required_evidence_env.issubset(set((scan_steps[0].get("env") or {}).keys())):
        problems.append(
            "nddev-security-bundle.yml: consolidated scan must supply all four "
            "actionlint/Zizmor/OSV/Gitleaks evidence paths"
        )
    evidence_uploads = [
        step for step in bundle_steps
        if isinstance(step, dict)
        and step.get("name") == "Upload redacted security evidence"
        and str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    if len(evidence_uploads) != 1 or (evidence_uploads[0].get("with") or {}).get("retention-days") != 1:
        problems.append(
            "nddev-security-bundle.yml: redacted evidence must upload exactly once with one-day retention"
        )

    for filename in sorted(isolated_checkout_workflows):
        workflow = load_yaml(workflow_root / filename)
        jobs = workflow.get("jobs", {}) or {}
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps", []) or []
            checkout_indexes = [
                index
                for index, step in enumerate(steps)
                if isinstance(step, dict)
                and str(step.get("uses", "")).startswith("actions/checkout@")
            ]
            if not checkout_indexes:
                continue
            isolation_indexes = [
                index
                for index, step in enumerate(steps)
                if isinstance(step, dict)
                and step.get("name") == "Isolate global Git config"
                and step.get("shell") == "bash"
                and step.get("run") == expected_isolation
            ]
            if len(isolation_indexes) != 1 or isolation_indexes[0] >= min(
                checkout_indexes
            ):
                problems.append(
                    f"{filename}: job {job_name!r} must run the canonical global "
                    "Git-config isolation exactly once before checkout"
                )

    # This repository is public. Every local reusable call that exposes a
    # runner selector must choose a standard hosted runner explicitly; relying
    # on the reusable's private-consumer default can route public PR code to the
    # private self-hosted fleet when that default changes or remains stale.
    #
    # "Standard hosted", not the literal string `ubuntu-latest`. The rule used
    # to demand that one label, which enforced the property by accident and
    # forbade `macos-latest` — a standard hosted runner, unmetered on public
    # repositories exactly like ubuntu. That made `swift-ci.yml`, whose whole
    # purpose is macOS, impossible to call from this repository's own fixture
    # estate. What matters is that the choice is explicit and lands on a runner
    # every account resolves and nobody is billed for; _runners.py holds that
    # definition, shared with check_examples.py.
    for filename in sorted(SELF_WORKFLOWS):
        caller = load_yaml(workflow_root / filename)
        for job_name, job in (caller.get("jobs", {}) or {}).items():
            if not isinstance(job, dict):
                continue
            use = str(job.get("uses", ""))
            prefix = "./.github/workflows/"
            if not use.startswith(prefix):
                continue
            reusable_path = workflow_root / use.removeprefix(prefix)
            reusable = load_yaml(reusable_path)
            reusable_on = get_on(reusable)
            call = (
                reusable_on.get("workflow_call", {})
                if isinstance(reusable_on, dict)
                else {}
            )
            inputs = call.get("inputs", {}) if isinstance(call, dict) else {}
            if not isinstance(inputs, dict) or "runner" not in inputs:
                continue
            with_values = job.get("with", {}) or {}
            chosen = with_values.get("runner") if isinstance(with_values, dict) else None
            if chosen is None:
                problems.append(
                    f"{filename}: public self-call job {job_name!r} must select a "
                    "standard hosted runner explicitly — inheriting the reusable's "
                    "default can route public pull-request code to a private fleet"
                )
                continue
            labels = resolve_runner_labels(chosen, job)
            if labels is None:
                problems.append(
                    f"{filename}: public self-call job {job_name!r} selects runner "
                    f"{chosen!r}, which this check cannot resolve to concrete "
                    "labels. Use a literal or `${{ matrix.KEY }}` with the values "
                    "listed in the job's own strategy.matrix — an unresolvable "
                    "expression is not evidence that the runner is free"
                )
                continue
            for label in labels:
                if not is_standard_hosted(label):
                    problems.append(
                        f"{filename}: public self-call job {job_name!r} can run on "
                        f"{label!r}, which is not a standard hosted runner. Standard "
                        "runners are unmetered on public repositories in all three "
                        "operating systems; larger runners are billed there from the "
                        "first minute, and a self-hosted label makes a forked pull "
                        "request remote code execution on that hardware"
                    )

    ci = load_yaml((workflow_files()[0].parent / "ci.yml"))
    jobs = ci.get("jobs", {}) or {}
    if "ci-gate" not in jobs:
        problems.append("ci.yml: missing required `ci-gate` job (branch-protection status check)")

    go_ci = load_yaml((workflow_files()[0].parent / "go-ci.yml"))
    go_on = get_on(go_ci)
    go_call = go_on.get("workflow_call", {}) if isinstance(go_on, dict) else {}
    go_inputs = go_call.get("inputs", {}) if isinstance(go_call, dict) else {}
    fetch_depth = go_inputs.get("fetch_depth", {}) if isinstance(go_inputs, dict) else {}
    if not isinstance(fetch_depth, dict) or (
        fetch_depth.get("type") != "number" or fetch_depth.get("default") != 1
    ):
        problems.append(
            "go-ci.yml: fetch_depth must remain a number with the "
            "backward-compatible default 1"
        )
    cache = go_inputs.get("cache", {}) if isinstance(go_inputs, dict) else {}
    if not isinstance(cache, dict) or (
        cache.get("type") != "boolean" or cache.get("default") is not True
    ):
        problems.append(
            "go-ci.yml: cache must remain a boolean with the "
            "backward-compatible default true"
        )
    go_steps = go_ci.get("jobs", {}).get("go", {}).get("steps", [])
    checkout = next(
        (
            step
            for step in go_steps
            if isinstance(step, dict) and step.get("name") == "Checkout"
        ),
        {},
    )
    checkout_with = checkout.get("with", {})
    actual_depth = (
        checkout_with.get("fetch-depth")
        if isinstance(checkout_with, dict)
        else None
    )
    if actual_depth != "${{ inputs.fetch_depth }}":
        problems.append(
            "go-ci.yml: Checkout must pass fetch_depth through to actions/checkout"
        )
    setup_go = next(
        (
            step
            for step in go_steps
            if isinstance(step, dict) and step.get("name") == "Set up Go"
        ),
        {},
    )
    setup_go_with = setup_go.get("with", {})
    actual_cache = (
        setup_go_with.get("cache")
        if isinstance(setup_go_with, dict)
        else None
    )
    if actual_cache != "${{ inputs.cache }}":
        problems.append(
            "go-ci.yml: Set up Go must pass cache through to actions/setup-go"
        )

    private_static = load_yaml((workflow_files()[0].parent / "private-static.yml"))
    static_steps = private_static.get("jobs", {}).get("static", {}).get("steps", [])
    steps_by_name = {step.get("name"): step for step in static_steps if isinstance(step, dict)}
    fail_fast_commands = {
        "Run install command": 'bash -euo pipefail -c "$INSTALL_COMMAND"',
        "Run validation": 'bash -euo pipefail -c "$VALIDATION_COMMAND"',
    }
    for name, expected in fail_fast_commands.items():
        actual = steps_by_name.get(name, {}).get("run")
        if actual != expected:
            problems.append(
                f"private-static.yml: {name!r} must use the fail-fast runner {expected!r}"
            )

    # The fail-fast contract above was written for private-static.yml alone
    # while 47 other caller-command sites across 23 workflows ran plain
    # `bash -c "$CMD"`. That inner shell inherits nothing from the step's
    # shell, so a caller passing `lint; test` or `build | tee log` got exit 0
    # from a failing first command — the reusable reported success for a build
    # that did not succeed. The rule is the same everywhere a caller's command
    # is executed, so it is enforced everywhere.
    problems += _fail_fast_caller_commands()
    problems += _balanced_caller_commands()
    problems += _runner_selftest()
    problems += _job_defaults_pin_the_shell()
    problems += _started_runs_are_preserved()
    problems += _download_attempts_are_bounded()
    return problems


BARE_BASH_C = re.compile(r'\bbash -c "(\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)"')
# Inputs whose value is handed to a shell by the reusable that receives it.
COMMAND_INPUT = re.compile(r"(^|_)commands?$")
DOWNLOAD_RETRY = re.compile(r"--retry[ =]([0-9]+)")


def _download_attempts_are_bounded() -> list[str]:
    """curl's retry count excludes the initial request; two means three attempts."""
    problems: list[str] = []
    paths = [*workflow_files(), *(Path("scripts").glob("*.sh"))]
    for path in paths:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            for match in DOWNLOAD_RETRY.finditer(line):
                if int(match.group(1)) > 2:
                    problems.append(
                        f"{path}:{lineno}: download retry count {match.group(1)} "
                        "exceeds two retries / three total attempts"
                    )
    return problems


def _started_runs_are_preserved() -> list[str]:
    """Every queued or started run must retain its own concurrency identity."""
    problems: list[str] = []
    paths = [*workflow_files(), *sorted(Path("examples").rglob("*.yml"))]
    for path in paths:
        workflow = load_yaml(path)
        concurrency = workflow.get("concurrency")
        if concurrency is None:
            continue
        group = concurrency.get("group") if isinstance(concurrency, dict) else None
        if (
            not isinstance(concurrency, dict)
            or concurrency.get("cancel-in-progress") is not False
            or not isinstance(group, str)
            or "github.run_id" not in group
        ):
            problems.append(
                f"{path}: concurrency must use github.run_id and set "
                "cancel-in-progress to literal false; GitHub retains only one "
                "pending run in a shared group, so ref grouping can erase evidence"
            )
    return problems


def _balanced_caller_commands() -> list[str]:
    """A command passed to a reusable must be shell-parseable.

    An unbalanced quote in one of these is invisible to every check this
    repository had: the YAML is valid, so actionlint passes; the value is just a
    string, so no schema complains; and the failure surfaces only when a runner
    reaches `bash: unexpected EOF while looking for matching \"`. That is a
    real minute of CI and a confusing log to reach a typo. `shlex` settles it in
    microseconds.

    This checks parseability, not safety: these strings are caller-authored by
    design, and the reusables run them through `bash -euo pipefail -c` on
    purpose.
    """
    problems: list[str] = []
    for path in workflow_files():
        for job_name, job in (load_yaml(path).get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            for key, value in (job.get("with") or {}).items():
                if not isinstance(value, str) or not COMMAND_INPUT.search(str(key)):
                    continue
                try:
                    shlex.split(value)
                except ValueError as exc:
                    problems.append(
                        f"{path.name}: job {job_name!r} input {key!r} is not "
                        f"shell-parseable ({exc}): {value[:70]!r}"
                    )
    return problems


def _fail_fast_caller_commands() -> list[str]:
    """Any `bash -c "$VAR"` running a caller command must set -euo pipefail."""
    problems: list[str] = []
    for path in workflow_files():
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = BARE_BASH_C.search(line)
            if match:
                problems.append(
                    f"{path.name}:{lineno}: `bash -c \"{match.group(1)}\"` does not "
                    "fail fast; use `bash -euo pipefail -c` so a caller command "
                    "like `a; b` or `a | b` cannot report success after failing"
                )
    return problems


def _runner_selftest() -> list[str]:
    """The shared runner predicate must keep saying no to the expensive answers.

    Widening this rule from the literal `ubuntu-latest` to "standard hosted" is
    only safe while the three things it was protecting against still fail:
    a larger runner (hosted, but billed on public repositories from the first
    minute), a self-hosted fleet label (a forked pull request becomes remote
    code execution on that hardware), and a missing or non-string value.
    """
    expectations = {
        # standard hosted, all three operating systems, latest and pinned
        "ubuntu-latest": True, "macos-latest": True, "windows-latest": True,
        "ubuntu-24.04": True, "macos-14": True, "windows-2022": True,
        # larger runners: hosted, never free
        "ubuntu-latest-8-cores": False, "ubuntu-latest-4-cores": False,
        "macos-latest-large": False, "windows-latest-xlarge": False,
        # somebody's fleet
        "nddev-linux-fast": False, "nddev-linux-release": False,
        "self-hosted": False, "amsterdam": False,
        # nothing at all
        "": False,
    }
    problems = []
    for label, expected in expectations.items():
        if is_standard_hosted(label) is not expected:
            problems.append(
                f"_runners.is_standard_hosted({label!r}) is "
                f"{is_standard_hosted(label)}, expected {expected}"
            )
    for value in (None, 123, ["ubuntu-latest"]):
        if is_standard_hosted(value):
            problems.append(
                f"_runners.is_standard_hosted({value!r}) accepted a non-string"
            )
    # Matrix resolution: a self-call may pick its runner from its own matrix,
    # but the check must see the values behind the expression. The dangerous
    # cases are an include: entry smuggling a fleet label past a clean `os:`
    # list, and an expression pointing at a matrix that does not exist — which
    # must read as "cannot tell", never as "fine".
    matrix_cases = [
        ({"strategy": {"matrix": {"os": ["ubuntu-latest", "windows-latest",
                                         "macos-latest"]}}},
         ["ubuntu-latest", "windows-latest", "macos-latest"]),
        ({"strategy": {"matrix": {"os": ["ubuntu-latest"],
                                  "include": [{"os": "nddev-linux-fast"}]}}},
         ["ubuntu-latest", "nddev-linux-fast"]),
        ({"strategy": {"matrix": {"other": ["ubuntu-latest"]}}}, None),
        ({}, None),
        ({"strategy": {"matrix": {"os": []}}}, None),
    ]
    for job, expected in matrix_cases:
        got = resolve_runner_labels("${{ matrix.os }}", job)
        if got != expected:
            problems.append(
                f"resolve_runner_labels(matrix.os, {job!r}) is {got!r}, "
                f"expected {expected!r}"
            )
    # A literal still resolves to itself; an unknown expression must not.
    if resolve_runner_labels("ubuntu-latest", {}) != ["ubuntu-latest"]:
        problems.append("resolve_runner_labels lost a literal label")
    if resolve_runner_labels("${{ inputs.runner }}", {}) is not None:
        problems.append(
            "resolve_runner_labels treated an unresolvable expression as decidable"
        )
    return problems


def _job_defaults_pin_the_shell() -> list[str]:
    """A job-level `defaults.run` must name its shell.

    A job-level `defaults.run` REPLACES the workflow-level one rather than
    merging with it key by key. The documentation describes per-name
    precedence, so this is easy to get wrong and impossible to see on Linux:
    twenty-six jobs here declared `defaults: run: working-directory:` and
    thereby dropped the `shell: bash` their own file declared three lines
    above. Linux hid it, because bash is the default there anyway.

    Windows does not hide it. A fixture run of python-ci on windows-latest
    executed its steps under PowerShell, where a bash line continuation and a
    `>>` redirect are syntax errors and `${VAR}` expands to nothing — the job
    printed "(requested )" and then failed. cross-platform-smoke.yml, the one
    workflow written for three operating systems, already set `shell: bash` on
    every individual step, which is the previous author reaching the same
    conclusion for one file.

    So: any job that declares `defaults.run` at all must also pin `shell`.
    """
    problems: list[str] = []
    for path in workflow_files():
        workflow = load_yaml(path)
        for job_name, job in (workflow.get("jobs", {}) or {}).items():
            if not isinstance(job, dict):
                continue
            run_defaults = ((job.get("defaults") or {}).get("run") or {})
            if not run_defaults:
                continue
            has_run_step = any(
                isinstance(step, dict) and "run" in step
                for step in (job.get("steps") or [])
            )
            if has_run_step and "shell" not in run_defaults:
                problems.append(
                    f"{path.name}: job {job_name!r} declares defaults.run without "
                    "`shell`. A job-level defaults.run replaces the workflow-level "
                    "one instead of merging, so this silently drops the file's own "
                    "`shell: bash` and every run step becomes PowerShell on Windows"
                )
    return problems


def main() -> int:
    problems = check()
    if problems:
        print("check_workflow_contracts: FAIL", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("check_workflow_contracts: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
