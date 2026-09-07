#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import tempfile

from ci_workflows_tools.sync_action_catalog import synchronize


def _write_catalog(root: pathlib.Path, sha: str, version: str) -> None:
    (root / "catalog/tools.yml").write_text(
        "tools:\n  - id: example\n    kind: action\n"
        f'    current_version: "{version}"\n    pin: "example/action@{sha}"\n',
        encoding="utf-8",
    )


def check() -> list[str]:
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as directory:
        root = pathlib.Path(directory)
        (root / ".github/workflows").mkdir(parents=True)
        (root / "catalog").mkdir()
        (root / "docs/generated").mkdir(parents=True)
        old = "a" * 40
        new = "b" * 40
        (root / ".github/workflows/ci.yml").write_text(
            f"jobs:\n  x:\n    steps:\n      - uses: example/action@{new} # v2.0.0\n",
            encoding="utf-8",
        )
        _write_catalog(root, old, "v1.0.0")
        (root / "catalog/action-images.yml").write_text(
            "images:\n  - action: example/action\n"
            "    image: docker://example/action:1.0.0\n",
            encoding="utf-8",
        )
        for relative in ("catalog/scorecard-evidence.yml", "docs/generated/scorecard-evidence.md"):
            (root / relative).write_text(f"example/action@{old}\n", encoding="utf-8")
        changed = synchronize(
            root,
            image_resolver=lambda action, sha: "docker://example/action:2.0.0",
        )
        if changed != [
            "catalog/tools.yml",
            "catalog/action-images.yml",
            "catalog/scorecard-evidence.yml",
            "docs/generated/scorecard-evidence.md",
        ]:
            problems.append(f"unexpected changed paths: {changed}")
        for relative in changed:
            text = (root / relative).read_text(encoding="utf-8")
            if relative != "catalog/action-images.yml" and (
                old in text or new not in text
            ):
                problems.append(f"{relative} did not converge")
        if "docker://example/action:2.0.0" not in (
            root / "catalog/action-images.yml"
        ).read_text(encoding="utf-8"):
            problems.append("transitive Docker image did not converge")
        if synchronize(root, image_resolver=lambda action, sha: "unexpected"):
            problems.append("second synchronization was not idempotent")

        # PR92 shape: every workflow file already shares one pin; catalog lags.
        # catalog-only must follow that unique pin and leave workflows untouched.
        old = "c" * 40
        new = "d" * 40
        (root / ".github/workflows/ci.yml").write_text(
            f"jobs:\n  x:\n    steps:\n      - uses: example/action@{new} # v2.0.0\n",
            encoding="utf-8",
        )
        (root / ".github/workflows/second.yml").write_text(
            f"jobs:\n  z:\n    steps:\n      - uses: example/action@{new} # v2.0.0\n",
            encoding="utf-8",
        )
        if (root / ".github/workflows/other.yml").exists():
            (root / ".github/workflows/other.yml").unlink()
        _write_catalog(root, old, "v1.0.0")
        before_ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        before_second = (root / ".github/workflows/second.yml").read_text(encoding="utf-8")
        changed = synchronize(
            root,
            image_resolver=lambda action, sha: "docker://example/action:2.0.0",
            catalog_only=True,
        )
        if any(path.startswith(".github/workflows/") for path in changed):
            problems.append("catalog-only unique-pin path rewrote a workflow file")
        if (root / ".github/workflows/ci.yml").read_text(encoding="utf-8") != before_ci:
            problems.append("catalog-only unique-pin path mutated ci.yml")
        if (root / ".github/workflows/second.yml").read_text(encoding="utf-8") != before_second:
            problems.append("catalog-only unique-pin path mutated second.yml")
        tools = (root / "catalog/tools.yml").read_text(encoding="utf-8")
        if f"example/action@{new}" not in tools or 'current_version: "v2.0.0"' not in tools:
            problems.append("catalog-only unique-pin path did not follow the shared workflow pin")

        # Mixed identities: catalog-only must fail closed and write nothing.
        (root / ".github/workflows/other.yml").write_text(
            f"jobs:\n  y:\n    steps:\n      - uses: example/action@{old} # v1.0.0\n",
            encoding="utf-8",
        )
        _write_catalog(root, old, "v1.0.0")
        before_other = (root / ".github/workflows/other.yml").read_text(encoding="utf-8")
        before_catalog = (root / "catalog/tools.yml").read_text(encoding="utf-8")
        raised = None
        try:
            synchronize(
                root,
                image_resolver=lambda action, sha: "docker://example/action:2.0.0",
                catalog_only=True,
            )
        except ValueError as exc:
            raised = exc
        if raised is None:
            problems.append("catalog-only mixed pins must fail closed")
        elif "mixed identities" not in str(raised):
            problems.append(f"catalog-only mixed pins raised unexpected: {raised}")
        if (root / ".github/workflows/other.yml").read_text(encoding="utf-8") != before_other:
            problems.append("catalog-only mixed pins mutated a workflow file")
        if (root / "catalog/tools.yml").read_text(encoding="utf-8") != before_catalog:
            problems.append("catalog-only mixed pins wrote a catalog pin the tree does not share")

        # Full sync still majority-rewrites stragglers for local/human use.
        changed = synchronize(
            root,
            image_resolver=lambda action, sha: "docker://example/action:2.0.0",
        )
        other = (root / ".github/workflows/other.yml").read_text(encoding="utf-8")
        if f"example/action@{new} # v2.0.0" not in other:
            problems.append("full synchronization did not rewrite the straggler workflow pin")
        if ".github/workflows/other.yml" not in changed:
            problems.append("full synchronization did not report the rewritten workflow")
    return problems


if __name__ == "__main__":
    found = check()
    if found:
        raise SystemExit("\n".join(found))
    print("sync-action-catalog-tests-ok")
